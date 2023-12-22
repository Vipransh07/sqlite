import sqlite3
import pandas as pd

df = pd.read_csv('cleaned_retail.csv')

connection = sqlite3.connect('retail.db')

df.to_sql('retail_data', connection, if_exists='replace')