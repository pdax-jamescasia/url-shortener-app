from flask import Flask, request, jsonify, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import text
from datetime import datetime, timedelta
from utils import get_secret
import random
import os
from dotenv import load_dotenv

app = Flask(__name__)


load_dotenv()

CLOUDSQL_CONNECTION_NAME = os.getenv('CLOUDSQL_CONNECTION_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = get_secret('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@/"
    f"{DB_NAME}?host=/cloudsql/{CLOUDSQL_CONNECTION_NAME}"
)
#app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@/cloudsql/{CLOUDSQL_CONNECTION_NAME}/{DB_NAME}'
# Initialize the database and migration
TABLE_NAME = 'url_mappings'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Define a URL model (this will map to a table in the DB)
class Url(db.Model):
    __tablename__ = TABLE_NAME
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(2048), nullable=False, unique = True)
    short_url = db.Column(db.String(6), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable = False)
 

def shorten(length = 7): 

    alph = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    alph_lower = alph.lower()

    new_url = ''

    for i in range(length):
        r = random.randint(0, len(alph)-1)
        if i%2 == 0:
            new_url += alph[r]
        else:
            new_url += alph_lower[r]

    return new_url 


@app.route('/urls', methods=['GET'])
def get_Urls():
    urls = Url.query.all()
    urls_list = [{"id": url.id, "original_url": url.original_url, "short_url": url.short_url, "created_at": url.created_at} for url in urls]
    return jsonify(urls_list)

@app.route('/urls/shorten', methods=['POST'])
def shortenURL():

    try:
        data = request.get_json()  # Get request data
        original_url = data.get('url').lower()

        if not original_url:
            return jsonify({'error':  'URL is required'}), 400
        
        # check if original_url in database
        url_map = Url.query.filter_by(original_url=original_url).first() 
        is_original_url_in_db = url_map != None

        if is_original_url_in_db:
            return jsonify({'url': url_map.short_url}), 202
        
        new_url = shorten()
        new_mapping = Url(original_url = original_url, short_url = new_url)  # Create new User instance
 

        # db.session.add(new_mapping)  # Add to session
        db.session.execute(text(f"INSERT INTO {TABLE_NAME}(original_url, short_url) values ('{original_url}','{new_url}');"))
        db.session.commit()  # Commit transaction

        return jsonify({'url': new_url}), 201
    
    except Exception as e:
        db.session.rollback()  # Rollback in case of error
        return jsonify({'error': str(e)}), 500


@app.route('/<short_url>', methods = ['GET'])
def redirect_to_long_url(short_url): 
    url_map = Url.query.filter_by(short_url = short_url).one_or_none()

    if url_map:
        return redirect(url_map.original_url, code=302)  # 302 for temporary redirect
    else:
        return  jsonify({'error': 'URL not found'}), 404



from apscheduler.schedulers.background import BackgroundScheduler

def delete_old_urls():
    """Deletes URLs older than 48 hours."""
    with app.app_context():  # Ensure the function runs within Flask's application context
        time_threshold = datetime.utcnow() - timedelta(hours=48)

        try:
            with db.engine.connect() as conn:
                result = conn.execute(text(f"DELETE FROM {TABLE_NAME} WHERE created_at < :time_threshold"), 
                                      {"time_threshold": time_threshold})
                conn.commit()
                print(f"Deleted {result.rowcount} old URLs.")
        except Exception as e:
            print(f"Error deleting old URLs: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(delete_old_urls, 'interval', hours=12)
scheduler.start()


if __name__ == '__main__':
    
    app.run(debug=True,port = 8080,host = '0.0.0.0') 
