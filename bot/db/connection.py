"""
Gestionnaire de connexion MySQL pour Veridian AI
Pattern standard à utiliser dans tout le projet
"""

import os
import mysql.connector
from mysql.connector import Error
from loguru import logger
from contextlib import contextmanager


def get_connection():
    """
    Crée et retourne une connexion MySQL.
    Utilise les variables d'environnement pour la configuration.
    
    Returns:
        mysql.connector.MySQLConnection: Connexion MySQL
        
    Raises:
        Error: Si la connexion échoue
    """
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            connection_timeout=10,
            autocommit=False
        )
        logger.debug(f"✓ Connexion MySQL établie vers {os.getenv('DB_HOST')}")
        return connection
    except Error as err:
        logger.error(f"✗ Erreur de connexion MySQL: {err}")
        raise


@contextmanager
def get_db_context():
    """
    Context manager pour gérer automatiquement les connexions MySQL.
    Assure la fermeture correcte de la connexion même en cas d'erreur.
    
    Usage:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM vai_guilds")
            results = cursor.fetchall()
    """
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception as e:
        logger.error(f"✗ Erreur DB: {e}")
        connection.rollback()
        raise
    finally:
        connection.close()
        logger.debug("✓ Connexion MySQL fermée")
