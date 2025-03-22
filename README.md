# 🌦️ Weather Data Pipeline

This project is an Airflow pipeline for retrieving and storing weather temperature data from Open Meteo, WeatherAPI, and Tomorrow.io into a PostgreSQL database. The pipeline fetches hourly temperature data, processes it, and stores it in structured tables for analysis and reporting.

## 🚀 Features
- Fetches weather temperature data from three sources: Open Meteo, WeatherAPI, and Tomorrow.io.
- Stores raw data in a `weather_data` table in PostgreSQL.
- Processes and organizes data into fact and dimension tables.
- Aggregates temperature data into daily, weekly, and monthly marts.
- Uses Apache Airflow for automation and scheduling.

## 🏛️ Database Schema
### Tables
1. **weather_data** (Raw hourly weather data)
   - `id` (TEXT, Primary Key)
   - `datetime` (TIMESTAMP)
   - `temperature` (FLOAT)
   - `area` (TEXT)
   - `source` (TEXT)
   - `created_at` (TIMESTAMP)

2. **fact_weather** (Fact table)
   - Stores processed weather data similar to `weather_data`

3. **dim_area** (Dimension table)
   - `area_id` (SERIAL, Primary Key)
   - `area_name` (TEXT, UNIQUE)

4. **mart_daily_weather** (Aggregated daily temperature)
   - `date` (DATE, Primary Key)
   - `avg_temperature` (FLOAT)
   - `area` (TEXT)

5. **mart_weekly_weather** (Aggregated weekly temperature)
   - `week_start` (DATE, Primary Key)
   - `avg_temperature` (FLOAT)
   - `area` (TEXT)

6. **mart_monthly_weather** (Aggregated monthly temperature)
   - `month_start` (DATE, Primary Key)
   - `avg_temperature` (FLOAT)
   - `area` (TEXT)

## ⚙️ Installation & Setup
### Prerequisites
- **Apache Airflow** (installed and running)
- **PostgreSQL** (database configured)
- **API Keys** for Open Meteo, WeatherAPI, and Tomorrow.io

### Configuration
1. Set up a PostgreSQL connection in Airflow (e.g., `rizqi-neon`).
2. Update API keys in the DAG script.
3. Deploy the DAG to your Airflow environment.

## 🔄 DAG Workflow
1. **Extract Data**: Fetches data from Open Meteo, WeatherAPI, and Tomorrow.io.
2. **Transform Data**: Ensures consistent datetime formats and removes duplicates.
3. **Load Data**: Stores data in `weather_data`.
4. **Create Fact & Dimension Tables**: Ensures required tables exist.
5. **Process Mart Data**: Aggregates data into daily, weekly, and monthly marts.

## ▶️ Running the Pipeline
1. Start the Airflow scheduler and webserver.
2. Trigger the DAG manually or set a schedule.
3. Monitor logs for errors.

## 📊 Dashboard Integration
The processed data can be visualized in **Metabase** with interactive filtering using the `datetime` column.

## Timezone Handling
- PostgreSQL stores UTC timestamps.
- Indonesian time (UTC+8) is applied when querying data in Metabase.

---

Feel free to discuss, Cheers 🍻.
