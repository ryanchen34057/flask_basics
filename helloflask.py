from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import socket
import threading
import uuid
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


# Sunmi 模式：產生收據純文字 (由前端 JS Bridge 送出列印)
@app.route('/pos/sunmi/receipt', methods=['POST'])
def pos_sunmi_receipt():
    data = request.get_json()
    store_name = data.get('store_name', '我的商店')
    items = data.get('items', [])
    total = data.get('total', 0)
    note = data.get('note', '')

    if not items:
        return jsonify(success=False, message='請至少新增一項商品')

    W = 32
    lines = []
    lines.append(store_name)
    lines.append('')
    lines.append('=' * W)

    for item in items:
        name = item.get('name', '')
        qty = item.get('qty', 1)
        price = item.get('price', 0)
        line_total = qty * price
        lines.append(name)
        detail = f'  {qty} x ${price}'
        total_str = f'${line_total}'
        spaces = max(1, W - len(detail) - len(total_str))
        lines.append(detail + ' ' * spaces + total_str)

    lines.append('=' * W)
    total_line = f'總計: ${total}'
    lines.append(' ' * max(0, W - len(total_line)) + total_line)
    lines.append('')

    if note:
        lines.append('-' * W)
        lines.append(f'備註: {note}')

    lines.append('')
    lines.append('        謝謝光臨！')
    lines.append('')

    return jsonify(success=True, text='\n'.join(lines))


# ============================================================
# 列印佇列系統 - 讓 Sunmi 自動輪詢並列印
# ============================================================
print_queue = []
print_queue_lock = threading.Lock()


# 提交列印任務到佇列
@app.route('/pos/queue/add', methods=['POST'])
def pos_queue_add():
    data = request.get_json()
    job_type = data.get('type', 'text')  # 'text' or 'receipt'
    job_id = str(uuid.uuid4())[:8]

    if job_type == 'receipt':
        store_name = data.get('store_name', '我的商店')
        items = data.get('items', [])
        total = data.get('total', 0)
        note = data.get('note', '')
        if not items:
            return jsonify(success=False, message='請至少新增一項商品')

        W = 32
        lines = []
        lines.append(store_name)
        lines.append('')
        lines.append('=' * W)
        for item in items:
            name = item.get('name', '')
            qty = item.get('qty', 1)
            price = item.get('price', 0)
            line_total = qty * price
            lines.append(name)
            detail = f'  {qty} x ${price}'
            total_str = f'${line_total}'
            spaces = max(1, W - len(detail) - len(total_str))
            lines.append(detail + ' ' * spaces + total_str)
        lines.append('=' * W)
        total_line = f'總計: ${total}'
        lines.append(' ' * max(0, W - len(total_line)) + total_line)
        lines.append('')
        if note:
            lines.append('-' * W)
            lines.append(f'備註: {note}')
        lines.append('')
        lines.append('        謝謝光臨！')
        lines.append('')
        text = '\n'.join(lines)
    else:
        text = data.get('content', '')
        if not text.strip():
            return jsonify(success=False, message='請輸入列印內容')

    job = {'id': job_id, 'type': job_type, 'text': text, 'created': datetime.now(timezone.utc).isoformat()}

    with print_queue_lock:
        print_queue.append(job)

    return jsonify(success=True, message=f'列印任務已加入佇列 (ID: {job_id})', job_id=job_id)


# Sunmi 輪詢：取得下一個列印任務
@app.route('/pos/queue/next', methods=['POST'])
def pos_queue_next():
    with print_queue_lock:
        if print_queue:
            job = print_queue.pop(0)
            return jsonify(has_job=True, job=job)
        else:
            return jsonify(has_job=False)


# 查看佇列狀態
@app.route('/pos/queue/status')
def pos_queue_status():
    with print_queue_lock:
        return jsonify(pending=len(print_queue), jobs=[j['id'] for j in print_queue])


# Sunmi 接收端頁面 (在 Sunmi POS 機上開啟)
@app.route('/pos/sunmi')
def pos_sunmi_receiver():
    return render_template('pos_sunmi_receiver.html')


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
    app.run(debug=True, host='0.0.0.0')

