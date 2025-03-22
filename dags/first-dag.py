from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.hooks.postgres_hook import PostgresHook
import pandas as pd

def extract_data():
    # Contoh data
    data = {'name': ['Alice', 'Bob', 'Charlie'], 'age': [24, 27, 22]}
    df = pd.DataFrame(data)
    return df.to_dict()

def store_data(**kwargs):
    df_dict = kwargs['ti'].xcom_pull(task_ids='extract_data')
    df = pd.DataFrame.from_dict(df_dict)

    hook = PostgresHook(postgres_conn_id='rizqi-neon')    
    conn = hook.get_conn()
    cursor = conn.cursor()

    # Buat tabel jika belum ada
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50),
            age INT
        )
    """)

    # Insert data ke tabel
    for _, row in df.iterrows():
        cursor.execute("INSERT INTO people (name, age) VALUES (%s, %s)", (row['name'], row['age']))

    conn.commit()
    cursor.close()
    conn.close()

# Definisikan default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 3, 17),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

# Inisialisasi DAG
dag = DAG(
    'first-dag',
    default_args=default_args,
    description='Contoh DAG Airflow sederhana',
    schedule_interval=timedelta(days=1),
    catchup=False,
)

# Definisikan task
extract_task = PythonOperator(
    task_id='extract_data',
    python_callable=extract_data,
    dag=dag,
)

store_task = PythonOperator(
    task_id='store_data',
    python_callable=store_data,
    provide_context=True,
    dag=dag,
)

# Atur urutan eksekusi
extract_task >> store_task
