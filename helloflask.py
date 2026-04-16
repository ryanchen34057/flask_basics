from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import socket
from pos_printer import print_receipt, print_text


app = Flask(__name__,template_folder = 'templates')

app.config.update(
    SECRET_KEY = 'A153r3bwpn',
    SQLALCHEMY_DATABASE_URI = 'sqlite:///catalog.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db = SQLAlchemy(app)

@app.route('/index')
@app.route('/')

def hello_flask():
    return "Hello flask!"

@app.route('/new/')
def query_strings(greeting = 'hello'):
    query_val = request.args.get('greeting',greeting)
    return '<h1> the greeting is : {0} </h1>'.format(query_val)

# strings
@app.route('/user')
@app.route('/user/<name>')
def no_query_strings(name='mina'):
    return '<h1> hello there! {} </h1>'.format(name)

# numbers
@app.route('/numbers/<int:num>')
def working_with_numbers(num):
    return '<h1> the number you picked is: ' + str(num) + '<h1>'
# numbers
@app.route('/add/<int:num1>/<int:num2>')
def adding_integers(num1,num2):
    return '<h1> the sum is: {}'.format(num1 + num2) + '</h1>'
#FLOATS
@app.route('/product/<float:num1>/<float:num2>')
def product(num1,num2):
    return '<h1> the product is : {}'.format(num1 * num2) + '</h1>'

# Using Templates
@app.route('/temp')
def using_templates():
    return render_template('hello.html')

# Jinja templates
@app.route('/watch')
def movies_2017():
    movie_list = ['autopsy of jane doe',
                  'neon demon',
                  'ghost in a shell',
                  'kong: skull island',
                  'john wick2',
                  'spiderman - homecoming']
    return render_template('movies.html',
                           movies = movie_list,
                           name = 'Harry')

# Tables
@app.route('/tables')
def movies_plus():
    movies_dict = {'autopsy of jane doe': 02.14,
                  'neon demon': 3.20,
                  'ghost in a shell': 1.50,
                  'kong: skull island': 3.50,
                  'john wick2': 02.52,
                  'spiderman - homecoming': 1.48}
    return render_template('table_data.html',
                           movies = movies_dict,
                           name = 'Sally')

# Filters
@app.route('/filters')
def filter_data():
    movies_dict = {'autopsy of jane doe': 02.14,
                  'neon demon': 3.20,
                  'ghost in a shell': 1.50,
                  'kong: skull island': 3.50,
                  'john wick2': 02.52,
                  'spiderman - homecoming': 1.48}
    return render_template('filter_data.html',
                           movies = movies_dict,
                           name = None,
                           film = 'a chrismas carol')

# POS 印表機控制台頁面
@app.route('/pos')
def pos_printer_page():
    return render_template('pos_printer.html')


# 測試印表機連線
@app.route('/pos/test', methods=['POST'])
def pos_test_connection():
    data = request.get_json()
    host = data.get('host', '')
    port = data.get('port', 9100)

    if not host:
        return jsonify(success=False, message='請輸入印表機 IP')

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((host, port))
        sock.close()
        return jsonify(success=True, message=f'連線成功！{host}:{port}')
    except socket.timeout:
        return jsonify(success=False, message=f'連線逾時：{host}:{port}')
    except ConnectionRefusedError:
        return jsonify(success=False, message=f'連線被拒絕：{host}:{port}')
    except OSError as e:
        return jsonify(success=False, message=f'連線失敗：{str(e)}')


# 列印收據
@app.route('/pos/print_receipt', methods=['POST'])
def pos_print_receipt():
    data = request.get_json()
    host = data.get('host', '')
    port = data.get('port', 9100)
    store_name = data.get('store_name', '我的商店')
    items = data.get('items', [])
    total = data.get('total', 0)
    note = data.get('note', '')

    if not host:
        return jsonify(success=False, message='請輸入印表機 IP')
    if not items:
        return jsonify(success=False, message='請至少新增一項商品')

    success, message = print_receipt(host, port, store_name, items, total, note)
    return jsonify(success=success, message=message)


# 純文字列印
@app.route('/pos/print_text', methods=['POST'])
def pos_print_text():
    data = request.get_json()
    host = data.get('host', '')
    port = data.get('port', 9100)
    content = data.get('content', '')

    if not host:
        return jsonify(success=False, message='請輸入印表機 IP')
    if not content.strip():
        return jsonify(success=False, message='請輸入列印內容')

    success, message = print_text(host, port, content)
    return jsonify(success=success, message=message)


@app.route('/macros')
def jinja_macros():
    movies_dict = {'autopsy of jane doe': 02.14,
                  'neon demon': 3.20,
                  'ghost in a shell': 1.50,
                  'kong: skull island': 3.50,
                  'john wick2': 02.52,
                  'spiderman - homecoming': 1.48}
    return render_template('using_macros.html',movies=movies_dict)

class Publication(db.Model):
    __tablename__ = 'publication'
    id = db.Column(db.Integer,primary_key=True)
    name = db.Column(db.String(80), nullable=False)

    def __init__(self,name):
        self.name = name

    def __repr__(self):
        return 'Publisher is {}'.format(self.name)

class Book(db.Model):
    __tablename__ = 'book'

    id = db.Column(db.Integer,primary_key = True)
    title = db.Column(db.String(500),nullable = False,index =True)
    author = db.Column(db.String(350))
    avg_rating = db.Column(db.Float)
    format = db.Column(db.String(50))
    image = db.Column(db.String(100),unique=True)
    num_pages = db.Column(db.Integer)
    pub_date = db.Column(db.DateTime,default=lambda: datetime.now(timezone.utc))

    # Relationship
    pub_id = db.Column(db.Integer, db.ForeignKey('publication.id'))

    def __init__(self,title,author,avg_rating,book_format,image,num_pages,pub_id):

        self.title = title
        self.author = author
        self.avg_rating = avg_rating
        self.format = book_format
        self.image = image
        self.num_pages = num_pages
        self.pub_id = pub_id

    def __repr__(self):
        return '{} by {}'.format(self.title,self.author)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

