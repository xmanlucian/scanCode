import pymysql
import configparser


def load_config():
    config = configparser.ConfigParser()
    config.read('server_config.ini')
    return config


def get_db_connection():
    config = load_config()
    return pymysql.connect(
        host=config.get('database', 'host'),
        user=config.get('database', 'user'),
        password=config.get('database', 'password'),
        database=config.get('database', 'database'),
        ssl={'ssl': {
            'ca': config.get('database', 'ssl_ca'),
        }
        }
    )


# 使用数据库连接
try:
    connection = get_db_connection()
    print("Database connected successfully!")
except pymysql.MySQLError as e:
    print(f"Error connecting to database: {e}")
