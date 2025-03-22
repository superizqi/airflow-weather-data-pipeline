from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.hooks.postgres_hook import PostgresHook
from datetime import datetime, timedelta
import requests
import pandas as pd
import hashlib
import logging

# **Default DAG Configuration**
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 3, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

dag = DAG(
    'weather-data-pipeline',
    default_args=default_args,
    description='Pipeline for retrieving and storing weather temperature data from Open Meteo, WeatherAPI, and Tomorrow.io into PostgreSQL',
    schedule_interval='@hourly',
    catchup=False
)

# ✅ 1️⃣ Function to Create Table If Not Exists
def create_table_if_not_exists():
    hook = PostgresHook(postgres_conn_id='CHANGE_WITH_YOUR_CONNECTION_ID')
    conn = hook.get_conn()
    cur = conn.cursor()

    create_table_query = """
    CREATE TABLE IF NOT EXISTS weather_data (
        id TEXT PRIMARY KEY,
        datetime TIMESTAMP,
        temperature FLOAT,
        area TEXT,
        source TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """
    cur.execute(create_table_query)
    conn.commit()
    cur.close()
    conn.close()

# ✅ 2️⃣ Function to fetch data from OpenMeteo
def fetch_weather_openmeteo():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": -6.2088,  # Jakarta
        "longitude": 106.8456,
        "hourly": "temperature_2m",
        "timezone": "Asia/Jakarta",
        "past_days": 7  # Only 7 days before now()
    }

    response = requests.get(url, params=params)
    data = response.json()
    
    # Convert To Dataframe
    df = pd.DataFrame({
        'datetime': pd.to_datetime(data['hourly']['time']),
        'temperature': data['hourly']['temperature_2m']
    })


    df['area'] = 'Jakarta'
    df['source'] = 'Open Meteo'
    df['created_at'] = datetime.utcnow()

    # Generate Unique ID
    df['id'] = df.apply(lambda row: hashlib.md5(f"{row['datetime']}{row['area']}{row['source']}".encode()).hexdigest(), axis=1)

    return df

# ✅ 3️⃣ Function to fetch data from weatherapi
def fetch_weather_weatherapi():
    API_KEY = "CHANGE_WITH_YOUR_API_KEY"  
    base_url = "http://api.weatherapi.com/v1/history.json"
    location = "Jakarta"
    
    # only 7 days before now()
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)

    all_data = []

    for i in range(7):
        date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
        url = f"{base_url}?key={API_KEY}&q={location}&dt={date}"

        response = requests.get(url)
        data = response.json()

        # Ambil data per jam
        for hour in data['forecast']['forecastday'][0]['hour']:
            all_data.append({
                'datetime': pd.to_datetime(hour['time']),
                'temperature': hour['temp_c'],
                'area': 'Jakarta',
                'source': 'WeatherAPI.com',
                'created_at': datetime.utcnow()
            })


    df = pd.DataFrame(all_data)

    # generate unique id
    df['id'] = df.apply(lambda row: hashlib.md5(f"{row['datetime']}{row['area']}{row['source']}".encode()).hexdigest(), axis=1)

    return df

def fetch_weather_tomorrow():
    TOMORROW_API_KEY = "CHANGE_WITH_YOUR_API_KEY"
    JAKARTA_LAT = -6.2088
    JAKARTA_LON = 106.8456
    url = f"https://api.tomorrow.io/v4/timelines"
    params = {
        "location": f"{JAKARTA_LAT},{JAKARTA_LON}",
        "fields": ["temperature"],
        "units": "metric",
        "timesteps": "1h",
        "apikey": TOMORROW_API_KEY
    }

    response = requests.get(url, params=params)
    data = response.json()

    if "data" not in data:
        raise ValueError("Invalid response from Tomorrow.io")

    records = []
    for interval in data["data"]["timelines"][0]["intervals"]:
        dt = interval["startTime"]
        temperature = interval["values"]["temperature"]

        records.append({
            "datetime": pd.to_datetime(dt),
            "temperature": temperature,
            "area": "Jakarta",
            "source": "Tomorrow.io",
            "created_at": datetime.utcnow()
        })

        dff = pd.DataFrame(records)
        dff['datetime'] = pd.to_datetime(dff['datetime']).dt.tz_localize(None)
        # create unique id
        dff['id'] = dff.apply(lambda row: hashlib.md5(f"{row['datetime']}{row['area']}{row['source']}".encode()).hexdigest(), axis=1)

    return dff

# ✅ 4️⃣ Function to check new data to prevent duplicates, then store to PostgreSQL
def check_and_insert_raw_data():
    hook = PostgresHook(postgres_conn_id='CHANGE_WITH_YOUR_CONNECTION_ID')
    conn = hook.get_conn()
    cur = conn.cursor()

    # fetch all data
    df_openmeteo = fetch_weather_openmeteo()
    df_weatherapi = fetch_weather_weatherapi()
    df_tomorrow = fetch_weather_tomorrow()

    expected_columns = ['id', 'datetime', 'temperature', 'area', 'source', 'created_at']

    df_openmeteo = df_openmeteo[expected_columns]
    df_weatherapi = df_weatherapi[expected_columns]
    df_tomorrow = df_tomorrow[expected_columns]

    df_openmeteo = df_openmeteo.reindex(columns=expected_columns)
    df_weatherapi = df_weatherapi.reindex(columns=expected_columns)
    df_tomorrow = df_tomorrow.reindex(columns=expected_columns)

    # make sure datetime format
    df_tomorrow['datetime'] = pd.to_datetime(df_tomorrow['datetime'])
    df_openmeteo['datetime'] = pd.to_datetime(df_openmeteo['datetime'])
    df_weatherapi['datetime'] = pd.to_datetime(df_weatherapi['datetime'])

    df_openmeteo["created_at"] = df_openmeteo["created_at"].astype("datetime64[ns]")
    df_weatherapi["created_at"] = df_weatherapi["created_at"].astype("datetime64[ns]")
    df_tomorrow["created_at"] = df_tomorrow["created_at"].astype("datetime64[ns]")


    logger = logging.getLogger("airflow.task")

    logger.info("🔍 OpenMeteo Columns: %s", df_openmeteo.columns)
    logger.info("🔍 WeatherAPI Columns: %s", df_weatherapi.columns)
    logger.info("🔍 Tomorrow.io Columns: %s", df_tomorrow.columns)

    logger.info("\n🔍 Data Types:\n%s", df_openmeteo.dtypes)
    logger.info("\n🔍 Data Types:\n%s", df_weatherapi.dtypes)
    logger.info("\n🔍 Data Types:\n%s", df_tomorrow.dtypes)

    logger.info("\n📊 Shape (Jumlah Data): OpenMeteo: %s, WeatherAPI: %s, Tomorrow.io: %s", 
                df_openmeteo.shape, df_weatherapi.shape, df_tomorrow.shape)


    # combine all data
    df = pd.concat([df_openmeteo, df_weatherapi, df_tomorrow], ignore_index=True)

    logger.info("\n🚀 Hasil Akhir (Gabungan DataFrame):\n%s", df.head().to_string())

    # id check, to filter only new data that want to be add
    cur.execute("SELECT id FROM weather_data")
    existing_ids = {row[0] for row in cur.fetchall()}  # Set agar pencarian cepat
    new_data = df[~df['id'].isin(existing_ids)].copy()

    if not new_data.empty:
        insert_query = """
        INSERT INTO weather_data (id, datetime, temperature, area, source, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.executemany(insert_query, [
            (
                row.id, 
                row.datetime.to_pydatetime(), 
                row.temperature, 
                row.area, 
                row.source, 
                row.created_at.to_pydatetime()
            ) for _, row in new_data.iterrows()
        ])
        conn.commit()

    cur.close()
    conn.close()

def create_insert_fact_tables():
    hook = PostgresHook(postgres_conn_id='CHANGE_WITH_CONNECTION_ID')
    conn = hook.get_conn()
    cur = conn.cursor()

    cur.execute("""
         CREATE TABLE IF NOT EXISTS fact_weather (
            id TEXT PRIMARY KEY,
            datetime TIMESTAMP,
            temperature FLOAT,
            area TEXT,
            source TEXT,
            created_at TIMESTAMP
        )
    """)
    
    cur.execute("""
        INSERT INTO fact_weather (id, datetime, temperature, area, source, created_at)
        SELECT id, datetime, temperature, area, source, created_at FROM weather_data
        ON CONFLICT (id) DO NOTHING
    """)

    conn.commit()
    cur.close()
    conn.close()

def create_insert_dim_tables():
    hook = PostgresHook(postgres_conn_id='CHANGE_WITH_CONNECTION_ID')
    conn = hook.get_conn()
    cur = conn.cursor()

    cur.execute("""
         CREATE TABLE IF NOT EXISTS dim_area (
            area_id SERIAL PRIMARY KEY,
            area_name TEXT UNIQUE
        )
    """)
    
    cur.execute("""
        INSERT INTO dim_area (area_name)
        SELECT DISTINCT area FROM weather_data
        ON CONFLICT (area_name) DO NOTHING
    """)

    conn.commit()
    cur.close()
    conn.close()


def create_insert_mart_tables():
    hook = PostgresHook(postgres_conn_id='CHANGE_WITH_CONNECTION_ID')
    conn = hook.get_conn()
    cur = conn.cursor()

    queries = [
        """
        CREATE TABLE IF NOT EXISTS mart_daily_weather (
            date DATE,
            avg_temperature FLOAT,
            area TEXT,
            PRIMARY KEY (date, area)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS mart_weekly_weather (
            week_start DATE,
            avg_temperature FLOAT,
            area TEXT,
            PRIMARY KEY (week_start, area)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS mart_monthly_weather (
            month_start DATE,
            avg_temperature FLOAT,
            area TEXT,
            PRIMARY KEY (month_start, area)
        )
        """
    ]
    
    for query in queries:
        cur.execute(query)

    # Delete existing data in marts to prevent duplication
    cur.execute("DELETE FROM mart_daily_weather")
    cur.execute("DELETE FROM mart_weekly_weather")
    cur.execute("DELETE FROM mart_monthly_weather")
    
    # Aggregate for marts
    cur.execute("""
        INSERT INTO mart_daily_weather (date, avg_temperature, area)
        SELECT DATE(datetime), AVG(temperature), area
        FROM weather_data
        GROUP BY DATE(datetime), area
    """)
    
    cur.execute("""
        INSERT INTO mart_weekly_weather (week_start, avg_temperature, area)
        SELECT DATE_TRUNC('week', datetime)::DATE, AVG(temperature), area
        FROM weather_data
        GROUP BY DATE_TRUNC('week', datetime)::DATE, area
    """)
    
    cur.execute("""
        INSERT INTO mart_monthly_weather (month_start, avg_temperature, area)
        SELECT DATE_TRUNC('month', datetime)::DATE, AVG(temperature), area
        FROM weather_data
        GROUP BY DATE_TRUNC('month', datetime)::DATE, area
    """)
    
    conn.commit()
    cur.close()
    conn.close()


# **Task Definitions**
fetch_weather_openmeteo_task = PythonOperator(
    task_id='fetch_weather_openmeteo',
    python_callable=fetch_weather_openmeteo,
    dag=dag
)

fetch_weather_weatherapi_task = PythonOperator(
    task_id='fetch_weather_weatherapi',
    python_callable=fetch_weather_weatherapi,
    dag=dag
)

fetch_weather_tomorrow_task = PythonOperator(
    task_id='fetch_weather_tomorrow',
    python_callable=fetch_weather_tomorrow,
    dag=dag
)

create_table_task = PythonOperator(
    task_id='create_table_if_not_exists',
    python_callable=create_table_if_not_exists,
    dag=dag
)

insert_weather_task = PythonOperator(
    task_id='check_and_insert_raw_data',
    python_callable=check_and_insert_raw_data,
    dag=dag
)

create_insert_fact_tables_task = PythonOperator(
    task_id='create_insert_fact_tables',
    python_callable=create_insert_fact_tables,
    dag=dag
)


create_insert_dim_tables_task = PythonOperator(
    task_id='create_insert_dim_tables',
    python_callable=create_insert_dim_tables,
    dag=dag
)

create_insert_mart_tables_task = PythonOperator(
    task_id='create_insert_mart_tables',
    python_callable=create_insert_mart_tables,
    dag=dag
)


# **Task Dependencies**
[fetch_weather_openmeteo_task, fetch_weather_weatherapi_task, fetch_weather_tomorrow_task] >> create_table_task >> insert_weather_task >> [create_insert_dim_tables_task, create_insert_fact_tables_task] >> create_insert_mart_tables_task
