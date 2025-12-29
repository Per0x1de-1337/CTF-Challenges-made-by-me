from flask import Flask, request, render_template
import os
import redis

app = Flask(__name__, static_url_path='/', static_folder='./static', template_folder='./templates')

@app.route('/')
def home():
    return "welcome to our http3 world of fun and get something for yourself from our shop for your life"

@app.route('/robots.txt')
def robots():
    return "are u a bot ?"

# In-memory state
r = redis.Redis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379/0'), decode_responses=True)

@app.route('/register', methods=['POST'])
def register():
    import uuid
    user_id = str(uuid.uuid4())
    user_key = f"user:{user_id}"
    r.hset(user_key, mapping={'balance': 0, 'total_transferred': 0, 'has_transferred': 0})
    return ({'user_id': user_id}, 200, {'Content-Type': 'application/json'})

@app.route('/api/transfer', methods=['POST'])
def transfer():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    amount = data.get('amount')
    is_early = request.headers.get('Early-Data') == '1'

    if not user_id or amount != 100:
        return ({'error': 'Invalid user_id or amount'}, 400, {'Content-Type': 'application/json'})

    user_key = f"user:{user_id}"
    with r.pipeline() as pipe:
        while True:
            try:
                pipe.watch(user_key)
                u = pipe.hgetall(user_key)
                if not u:
                    pipe.multi()
                    pipe.hset(user_key, mapping={'balance': 0, 'total_transferred': 0, 'has_transferred': 0})
                    pipe.execute()
                    continue
                balance = int(u.get('balance', 0))
                total = int(u.get('total_transferred', 0))
                has = int(u.get('has_transferred', 0))
                if not is_early and has:
                    pipe.unwatch()
                    return ({'error': 'One transfer only!'}, 400, {'Content-Type': 'application/json'})
                if balance < 100:
                    pipe.unwatch()
                    return ({'error': 'Insufficient funds'}, 400, {'Content-Type': 'application/json'})
                pipe.multi()
                pipe.hincrby(user_key, 'balance', -100)
                pipe.hincrby(user_key, 'total_transferred', 100)
                pipe.hset(user_key, 'has_transferred', 1)
                pipe.execute()
                break
            except redis.exceptions.WatchError:
                continue
    vals = r.hmget(user_key, ['total_transferred', 'balance'])
    tt = int(vals[0]) if vals[0] is not None else 0
    bal = int(vals[1]) if vals[1] is not None else 0
    return ({
        'success': True,
        'total_transferred': tt,
        'balance': bal
    }, 200, {'Content-Type': 'application/json'})

@app.route('/api/redeem', methods=['POST'])
def redeem():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    is_early = request.headers.get('Early-Data') == '1'

    if not user_id:
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})

    user_key = f"user:{user_id}"
    with r.pipeline() as pipe:
        while True:
            try:
                pipe.watch(user_key)
                u = pipe.hgetall(user_key)
                if not u:
                    pipe.multi()
                    pipe.hset(user_key, mapping={'balance': 0, 'total_transferred': 0, 'has_transferred': 0, 'redeem_count': 0})
                    pipe.execute()
                    continue
                redeem_count = int(u.get('redeem_count', 0))
                if not is_early and redeem_count >= 1:
                    pipe.unwatch()
                    return ({'error': 'only one transfer huh!!'}, 400, {'Content-Type': 'application/json'})
                pipe.multi()
                pipe.hincrby(user_key, 'balance', 100)
                pipe.hincrby(user_key, 'redeem_count', 1)
                pipe.execute()
                break
            except redis.exceptions.WatchError:
                continue
    bal = int(r.hget(user_key, 'balance') or 0)
    remaining = max(0, 500 - bal)
    return ({
        'success': True,
        'credited': 100,
        'balance': bal,
        'can_afford_flag': bal >= 500,
        'remaining': remaining
    }, 200, {'Content-Type': 'application/json'})

@app.route('/balance')
def balance():
    user_id = request.args.get('user_id')
    if not user_id:
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    user_key = f"user:{user_id}"
    if not r.exists(user_key):
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    bal = int(r.hget(user_key, 'balance') or 0)
    return ({'balance': bal}, 200, {'Content-Type': 'application/json'})

@app.route('/api/balance')
def api_balance():
    user_id = request.args.get('user_id')
    if not user_id:
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    user_key = f"user:{user_id}"
    if not r.exists(user_key):
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    bal = int(r.hget(user_key, 'balance') or 0)
    return ({'balance': bal}, 200, {'Content-Type': 'application/json'})

@app.route('/api/shop')
def api_shop():
    items = {'fame': 50, 'power': 70, 'respect': 90, 'flag': 500}
    return ({'items': [{'item': k, 'price': v} for k, v in items.items()]}, 200, {'Content-Type': 'application/json'})

@app.route('/api/inventory')
def api_inventory():
    user_id = request.args.get('user_id')
    if not user_id:
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    inv_key = f"inv:{user_id}"
    items = list(r.smembers(inv_key) or [])
    return ({'inventory': sorted(items)}, 200, {'Content-Type': 'application/json'})

@app.route('/api/buy', methods=['POST'])
def api_buy():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    item = data.get('item')
    if not user_id or not item:
        return ({'error': 'Invalid user_id or item'}, 400, {'Content-Type': 'application/json'})
    price_map = {'fame': 50, 'respect': 70, 'power': 90, 'flag': 500}
    if item not in price_map:
        return ({'error': 'Unknown item'}, 400, {'Content-Type': 'application/json'})
    price = price_map[item]

    user_key = f"user:{user_id}"
    inv_key = f"inv:{user_id}"
    with r.pipeline() as pipe:
        while True:
            try:
                pipe.watch(user_key, inv_key)
                u = pipe.hgetall(user_key)
                if not u:
                    pipe.multi()
                    pipe.hset(user_key, mapping={'balance': 0, 'total_transferred': 0, 'has_transferred': 0, 'redeem_count': 0})
                    pipe.execute()
                    continue
                bal = int(u.get('balance', 0))
                already_owned = r.sismember(inv_key, item)
                if already_owned:
                    pipe.unwatch()
                    return ({'error': 'Already owned'}, 400, {'Content-Type': 'application/json'})
                if bal < price:
                    pipe.unwatch()
                    return ({'error': 'Insufficient funds'}, 400, {'Content-Type': 'application/json'})
                pipe.multi()
                pipe.hincrby(user_key, 'balance', -price)
                pipe.sadd(inv_key, item)
                pipe.execute()
                break
            except redis.exceptions.WatchError:
                continue

    if item == 'flag':
        return ({'flag': 'FLAG{0rtt_replay_attacks_4r3_c00l}', 'item': 'flag', 'price': price}, 200, {'Content-Type': 'application/json'})
    return ({'purchased': item, 'price': price}, 200, {'Content-Type': 'application/json'})

@app.route('/api/progress')
def progress():
    user_id = request.args.get('user_id')
    if not user_id:
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    user_key = f"user:{user_id}"
    if not r.exists(user_key):
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    bal = int(r.hget(user_key, 'balance') or 0)
    remaining = max(0, 500 - bal)
    inv_key = f"inv:{user_id}"
    flag_owned = r.sismember(inv_key, 'flag')
    return ({
        'balance': bal,
        'remaining': remaining,
        'flag_ready': bal >= 500,
        'can_afford_flag': bal >= 500,
        'flag_owned': bool(flag_owned)
    }, 200, {'Content-Type': 'application/json'})

@app.route('/total')
def total():
    user_id = request.args.get('user_id')
    if not user_id:
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    user_key = f"user:{user_id}"
    if not r.exists(user_key):
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    tt = int(r.hget(user_key, 'total_transferred') or 0)
    return ({'total_transferred': tt}, 200, {'Content-Type': 'application/json'})

@app.route('/flag')
def flag():
    user_id = request.args.get('user_id')
    if not user_id:
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    user_key = f"user:{user_id}"
    if not r.exists(user_key):
        return ({'error': 'Invalid user_id'}, 400, {'Content-Type': 'application/json'})
    inv_key = f"inv:{user_id}"
    if r.sismember(inv_key, 'flag'):
        return ({'flag': 'FLAG{0rtt_replay_attacks_4r3_c00l}'}, 200, {'Content-Type': 'application/json'})
    return ({'error': 'Purchase flag via /api/buy'}, 403, {'Content-Type': 'application/json'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
