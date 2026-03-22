from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os
import hashlib
import requests
import json
import threading
import time
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'surubox-secret-key-2024')

# Database Configuration
database_url = os.environ.get('DATABASE_URL', 'sqlite:///surubox.db')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== YOYOMEDIA API CONFIG ====================
API_URL = 'https://yoyomedia.in/api/v2'
API_KEY = '69c8df96bffab4dabdff7ac2efe0dcfa0be8d46d521e7f24a8bb49c4ba974ed5'
LIKES_ID = '12876'
VIEWS_ID = '13636'

# ==================== DATABASE MODELS ====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    name = db.Column(db.String(100))
    daily_limit = db.Column(db.Integer, default=5)
    orders_today = db.Column(db.Integer, default=0)
    last_reset = db.Column(db.Date, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    api_id = db.Column(db.String(50), nullable=False)
    min_order = db.Column(db.Integer, default=10)
    max_order = db.Column(db.Integer, default=10000)
    enabled = db.Column(db.Boolean, default=True)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, default=1)
    hour_0 = db.Column(db.Integer, default=100)
    hour_1 = db.Column(db.Integer, default=120)
    hour_2 = db.Column(db.Integer, default=140)
    hour_3 = db.Column(db.Integer, default=160)
    hour_4 = db.Column(db.Integer, default=180)
    hour_5 = db.Column(db.Integer, default=200)
    hour_6 = db.Column(db.Integer, default=220)
    hour_7 = db.Column(db.Integer, default=240)
    hour_8 = db.Column(db.Integer, default=260)
    hour_9 = db.Column(db.Integer, default=280)
    hour_10 = db.Column(db.Integer, default=300)
    hour_11 = db.Column(db.Integer, default=320)
    hour_12 = db.Column(db.Integer, default=340)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    url = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, default=0)
    api_order_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

# ==================== HELPER FUNCTIONS ====================
def call_yoyomedia_api(service_id, link, quantity):
    """Call YoYoMedia API"""
    try:
        response = requests.post(API_URL, data={
            'key': API_KEY,
            'action': 'add',
            'service': service_id,
            'link': link,
            'quantity': quantity
        }, timeout=30)
        return response.json()
    except Exception as e:
        return {'error': str(e)}

def reset_daily_limits():
    """Reset daily order counts for all users"""
    with app.app_context():
        today = date.today()
        users = User.query.all()
        for user in users:
            if user.last_reset != today:
                user.orders_today = 0
                user.last_reset = today
        db.session.commit()

def process_pending_orders():
    """Background task to process pending orders"""
    with app.app_context():
        orders = Order.query.filter(Order.status.in_(['pending', 'processing'])).all()
        for order in orders:
            service = Service.query.get(order.service_id)
            if service and service.enabled:
                result = call_yoyomedia_api(service.api_id, order.url, order.quantity)
                if 'order' in result:
                    order.api_order_id = result['order']
                    order.status = 'processing'
                elif 'error' in result:
                    order.status = 'failed'
            db.session.commit()

# ==================== CREATE DATABASE TABLES ====================
with app.app_context():
    db.create_all()
    
    # Create default admin
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=hashlib.md5('admin123'.encode()).hexdigest(),
            role='admin',
            name='Administrator',
            daily_limit=999
        )
        db.session.add(admin)
    
    # Create default users
    default_users = [
        ('rahul', 'rahul123', 'Rahul', 5),
        ('priya', 'priya123', 'Priya', 10),
        ('amit', 'amit123', 'Amit', 0)
    ]
    for u, p, n, l in default_users:
        if not User.query.filter_by(username=u).first():
            user = User(
                username=u,
                password=hashlib.md5(p.encode()).hexdigest(),
                role='user',
                name=n,
                daily_limit=l
            )
            db.session.add(user)
    
    # Create default services
    default_services = [
        ('Instagram Followers', 'IG-FOLLOW-001', 10, 10000, True),
        ('Instagram Likes', LIKES_ID, 10, 5000, True),
        ('Instagram Views', VIEWS_ID, 50, 50000, True),
        ('Instagram Comments', 'IG-COMMENT-001', 5, 1000, False),
        ('Instagram Shares', 'IG-SHARE-001', 5, 1000, False)
    ]
    for name, api_id, min_o, max_o, enabled in default_services:
        if not Service.query.filter_by(name=name).first():
            service = Service(
                name=name,
                api_id=api_id,
                min_order=min_o,
                max_order=max_o,
                enabled=enabled
            )
            db.session.add(service)
    db.session.commit()
    
    # Create default schedule
    if not Schedule.query.first():
        schedule = Schedule()
        db.session.add(schedule)
        db.session.commit()

# ==================== START SCHEDULER ====================
scheduler = BackgroundScheduler()
scheduler.add_job(func=reset_daily_limits, trigger="cron", hour=0, minute=0)
scheduler.add_job(func=process_pending_orders, trigger="interval", minutes=30)
scheduler.start()

# ==================== HTML TEMPLATE ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SURU-BOX | SMM Panel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Courier New', monospace;
            background: #0a0a0a;
            color: #00ff00;
            min-height: 100vh;
        }
        .matrix-bg {
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: repeating-linear-gradient(0deg, #00ff0010 0px, #00ff0010 2px, transparent 2px, transparent 6px);
            pointer-events: none;
            z-index: 0;
            animation: matrixScroll 20s linear infinite;
        }
        @keyframes matrixScroll {
            0% { background-position: 0 0; }
            100% { background-position: 0 100%; }
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            position: relative;
            z-index: 1;
        }
        .header {
            border: 2px solid #00ff00;
            padding: 20px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #000000cc;
            backdrop-filter: blur(5px);
            animation: borderPulse 2s infinite;
        }
        @keyframes borderPulse {
            0%, 100% { border-color: #00ff00; box-shadow: 0 0 20px #00ff00; }
            50% { border-color: #00cc00; box-shadow: 0 0 40px #00ff00; }
        }
        .logo { font-size: 28px; letter-spacing: 5px; }
        .logo span { animation: blink 1s infinite; }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        .tabs { display: flex; gap: 10px; margin-bottom: 30px; flex-wrap: wrap; }
        .tab-btn {
            padding: 12px 24px;
            background: #000;
            border: 1px solid #00ff00;
            color: #00ff00;
            cursor: pointer;
            font-family: monospace;
            transition: all 0.3s;
        }
        .tab-btn:hover, .tab-btn.active { background: #00ff00; color: #000; box-shadow: 0 0 20px #00ff00; }
        .tab-content { display: none; animation: fadeIn 0.3s; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
        .card {
            border: 1px solid #00ff00;
            background: #000000cc;
            backdrop-filter: blur(5px);
            margin-bottom: 25px;
        }
        .card-header {
            padding: 15px 20px;
            border-bottom: 1px solid #00ff00;
            background: #00ff0010;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-header h3 { font-size: 18px; }
        .card-body { padding: 20px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        .stat-card {
            border: 1px solid #00ff00;
            padding: 20px;
            text-align: center;
            background: #000;
        }
        .stat-number { font-size: 36px; font-weight: bold; }
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; margin-bottom: 5px; font-size: 12px; }
        .hacker-input {
            width: 100%;
            padding: 12px;
            background: #000;
            border: 1px solid #00ff00;
            color: #00ff00;
            font-family: monospace;
            outline: none;
        }
        .hacker-input:focus { box-shadow: 0 0 15px #00ff00; }
        .btn-hacker {
            padding: 12px 24px;
            background: #000;
            border: 1px solid #00ff00;
            color: #00ff00;
            cursor: pointer;
            font-family: monospace;
            transition: all 0.3s;
        }
        .btn-hacker:hover { background: #00ff00; color: #000; box-shadow: 0 0 20px #00ff00; }
        .data-table { width: 100%; border-collapse: collapse; }
        .data-table th, .data-table td {
            border: 1px solid #00ff00;
            padding: 10px;
            text-align: left;
        }
        .data-table th { background: #00ff0010; }
        .data-table tr:hover { background: #00ff0010; }
        .schedule-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
        }
        .schedule-item {
            border: 1px solid #00ff00;
            padding: 10px;
            text-align: center;
            background: #000;
        }
        .schedule-item input {
            width: 100%;
            padding: 8px;
            background: #000;
            border: 1px solid #00ff00;
            color: #00ff00;
            margin-top: 5px;
            text-align: center;
        }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            font-size: 11px;
            border: 1px solid;
            border-radius: 3px;
        }
        .badge-processing { border-color: #ffaa00; color: #ffaa00; }
        .badge-completed { border-color: #00ff00; color: #00ff00; }
        .badge-pending { border-color: #ff6600; color: #ff6600; }
        .login-container {
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-box {
            border: 2px solid #00ff00;
            padding: 40px;
            width: 400px;
            text-align: center;
            background: #000;
            animation: glowPulse 2s infinite;
        }
        @keyframes glowPulse { 0%,100%{box-shadow:0 0 30px #00ff00} 50%{box-shadow:0 0 60px #00ff00} }
        .login-box h1 { margin-bottom: 30px; letter-spacing: 5px; }
        .login-box input {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            background: #000;
            border: 1px solid #00ff00;
            color: #00ff00;
            font-family: monospace;
        }
        .login-box button {
            width: 100%;
            padding: 12px;
            margin: 20px 0;
            background: #000;
            border: 2px solid #00ff00;
            color: #00ff00;
            cursor: pointer;
            font-size: 16px;
        }
        .login-box button:hover { background: #00ff00; color: #000; }
        .message {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 15px 25px;
            border: 1px solid #00ff00;
            background: #000;
            display: none;
            z-index: 1000;
            animation: slideIn 0.3s;
        }
        @keyframes slideIn { from{transform:translateX(100%)} to{transform:translateX(0)} }
        .message.success { border-color: #00ff00; color: #00ff00; background: #00ff0010; }
        .message.error { border-color: #ff0000; color: #ff0000; background: #ff000010; }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #00ff00;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 768px) { .schedule-grid { grid-template-columns: repeat(2, 1fr); } }
    </style>
</head>
<body>
<div class="matrix-bg"></div>
<div class="container">
    <div id="loginPage" class="login-container">
        <div class="login-box">
            <h1>⚡ SURU-BOX ⚡</h1>
            <input type="text" id="loginUser" placeholder="USERNAME" value="admin">
            <input type="password" id="loginPass" placeholder="PASSWORD" value="admin123">
            <button onclick="login()">LOGIN</button>
            <div style="margin-top:20px; font-size:12px; opacity:0.7;">Admin: admin/admin123 | User: rahul/rahul123</div>
        </div>
    </div>
    
    <div id="mainApp" style="display:none;">
        <div class="header">
            <div class="logo">SURU<span>_</span>BOX</div>
            <div><span id="userNameDisplay"></span> <button class="btn-hacker" onclick="logout()" style="margin-left:15px;">LOGOUT</button></div>
        </div>
        <div class="tabs" id="tabsContainer"></div>
        <div id="dashboardTab" class="tab-content"><div class="stats-grid" id="statsGrid"></div></div>
        <div id="orderTab" class="tab-content">
            <div class="card">
                <div class="card-header"><h3>📥 EXECUTE ORDER</h3><span>YoYoMedia API</span></div>
                <div class="card-body">
                    <div class="input-group"><label>🔧 SELECT SERVICE</label><select id="orderService" class="hacker-input"></select></div>
                    <div class="input-group"><label>🔗 INSTAGRAM POST URL</label><input type="url" id="orderUrl" class="hacker-input" placeholder="https://www.instagram.com/p/..."></div>
                    <div class="input-group"><label>📊 QUANTITY</label><input type="number" id="orderQty" class="hacker-input" value="100"></div>
                    <button class="btn-hacker" id="placeBtn" onclick="placeOrder()" style="width:100%;padding:15px;font-size:16px;">🚀 EXECUTE ORDER</button>
                </div>
            </div>
            <div class="card"><div class="card-header"><h3>📋 YOUR ORDERS</h3></div><div class="card-body"><div id="userOrdersList"></div></div></div>
        </div>
        <div id="usersTab" class="tab-content"><div class="card"><div class="card-header"><h3>👥 USER MANAGEMENT</h3></div><div class="card-body"><div id="usersList"></div></div></div></div>
        <div id="servicesTab" class="tab-content"><div class="card"><div class="card-header"><h3>🔧 SERVICES & API SETTINGS</h3></div><div class="card-body"><div id="servicesList"></div><button class="btn-hacker" onclick="testAPI()" style="margin-top:15px;">🔌 TEST API CONNECTION</button></div></div></div>
        <div id="scheduleTab" class="tab-content"><div class="card"><div class="card-header"><h3>⏰ HOURLY DELIVERY SCHEDULE</h3></div><div class="card-body"><div class="schedule-grid" id="scheduleGrid"></div><button class="btn-hacker" onclick="saveSchedule()" style="margin-top:20px;width:100%;">💾 SAVE SCHEDULE</button></div></div></div>
        <div id="ordersTab" class="tab-content"><div class="card"><div class="card-header"><h3>📦 ALL ORDERS</h3></div><div class="card-body"><div id="allOrdersList"></div></div></div></div>
    </div>
</div>
<div id="messageToast" class="message"></div>

<script>
let currentUser = null;
function showMsg(msg, type) { let t=document.getElementById('messageToast'); t.className='message '+type; t.innerHTML=msg; t.style.display='block'; setTimeout(()=>t.style.display='none',4000); }
function callAPI(action, data, cb) {
    let fd=new FormData(); fd.append('action',action);
    for(let k in data) fd.append(k,data[k]);
    fetch(window.location.href,{method:'POST',body:fd}).then(r=>r.json()).then(d=>{if(cb)cb(d);}).catch(e=>showMsg('Error','error'));
}
function login() {
    let u=document.getElementById('loginUser').value, p=document.getElementById('loginPass').value;
    callAPI('login',{username:u,password:p},d=>{if(d.success){currentUser={role:d.role}; document.getElementById('loginPage').style.display='none'; document.getElementById('mainApp').style.display='block'; loadApp();}else{showMsg('Invalid credentials','error');}});
}
function logout(){ callAPI('logout',{},()=>{location.reload();}); }
function loadApp(){
    let isAdmin=currentUser.role==='admin';
    document.getElementById('tabsContainer').innerHTML=`<button class="tab-btn active" onclick="switchTab('dashboard')">📊 DASHBOARD</button><button class="tab-btn" onclick="switchTab('order')">📥 ORDER</button>`+(isAdmin?`<button class="tab-btn" onclick="switchTab('users')">👥 USERS</button><button class="tab-btn" onclick="switchTab('services')">🔧 SERVICES</button><button class="tab-btn" onclick="switchTab('schedule')">⏰ SCHEDULE</button><button class="tab-btn" onclick="switchTab('orders')">📦 ORDERS</button>`:'');
    loadUserInfo(); loadStats(); loadServices(); loadUserOrders();
    if(isAdmin){ loadUsers(); loadAllServices(); loadSchedule(); loadAllOrders(); }
}
function switchTab(t){ document.querySelectorAll('.tab-content').forEach(tab=>tab.classList.remove('active')); document.getElementById(t+'Tab').classList.add('active'); event.target.classList.add('active'); }
function loadUserInfo(){ callAPI('get_user',{},d=>{if(d.success) document.getElementById('userNameDisplay').innerHTML=`👤 ${d.user.name} | 📊 ${d.user.orders_today}/${d.user.daily_limit===0?'∞':d.user.daily_limit}`;}); }
function loadStats(){ callAPI('get_stats',{},d=>{document.getElementById('statsGrid').innerHTML=`<div class="stat-card"><div class="stat-number">${d.total_users||0}</div><div>Total Users</div></div><div class="stat-card"><div class="stat-number">${d.total_orders||0}</div><div>Total Orders</div></div><div class="stat-card"><div class="stat-number">${d.active_orders||0}</div><div>Active Orders</div></div><div class="stat-card"><div class="stat-number">${d.today_orders||0}</div><div>Today's Orders</div></div>`;}); }
function loadServices(){ callAPI('get_services',{},d=>{let h=''; d.services.forEach(s=>{h+=`<option value="${s.id}" data-min="${s.min_order}" data-max="${s.max_order}">${s.name} (${s.min_order}-${s.max_order})</option>`;}); document.getElementById('orderService').innerHTML=h;}); }
function placeOrder(){
    let btn=document.getElementById('placeBtn'), orig=btn.innerHTML;
    if(!document.getElementById('orderUrl').value){ showMsg('Please enter URL!','error'); return; }
    btn.innerHTML='<span class="loading"></span> PROCESSING...'; btn.disabled=true;
    callAPI('place_order',{service_id:document.getElementById('orderService').value, url:document.getElementById('orderUrl').value, quantity:document.getElementById('orderQty').value},d=>{
        btn.innerHTML=orig; btn.disabled=false;
        if(d.success){ showMsg('✅ Order placed! Order ID: '+d.order_id,'success'); document.getElementById('orderUrl').value=''; loadUserOrders(); loadUserInfo(); }
        else showMsg(d.message||'Failed to place order!','error');
    });
}
function loadUserOrders(){ callAPI('get_orders',{},d=>{if(d.orders?.length){let h='<table class="data-table"> <thead> <tr><th>Order ID</th><th>Service</th><th>Quantity</th><th>Status</th><th>Date</th></tr> </thead> <tbody>'; d.orders.forEach(o=>{let badgeClass=o.status==='completed'?'badge-completed':(o.status==='processing'?'badge-processing':'badge-pending'); h+=`<tr><td>${o.order_id}</td><td>${o.service_name}</td><td>${o.quantity}</td><td><span class="badge ${badgeClass}">${o.status}</span></td><td>${o.created_at?.substring(0,10)}</td></tr>`;}); h+='</tbody></table>'; document.getElementById('userOrdersList').innerHTML=h;}else{document.getElementById('userOrdersList').innerHTML='<p>No orders yet</p>';}}); }
function loadUsers(){ callAPI('get_users',{},d=>{let h='<table class="data-table"><thead><tr><th>ID</th><th>Username</th><th>Role</th><th>Daily Limit</th><th>Today</th><th>Actions</th></tr></thead><tbody>'; d.users.forEach(u=>{h+=`<tr><td>${u.id}</td><td>${u.username}</td><td>${u.role}</td><td><input type="number" id="limit_${u.id}" value="${u.daily_limit}" style="width:80px;background:#000;border:1px solid #0f0;color:#0f0;" onchange="updateUserLimit(${u.id})"></td><td>${u.orders_today}</td><td><button class="btn-hacker" style="padding:5px 10px;" onclick="resetUser(${u.id})">Reset</button> ${u.username!='admin'?`<button class="btn-hacker" style="padding:5px 10px;" onclick="deleteUser(${u.id})">Delete</button>`:''}</td></tr>`;}); h+='</tbody></table><div style="margin-top:20px; padding:15px; border:1px solid #0f0;"><h4>➕ ADD NEW USER</h4><div style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px;"><input type="text" id="newUser" placeholder="Username" class="hacker-input"><input type="password" id="newPass" placeholder="Password" class="hacker-input"><select id="newRole" class="hacker-input"><option value="user">User</option><option value="admin">Admin</option></select><input type="number" id="newLimit" placeholder="Limit" value="5" class="hacker-input"></div><button class="btn-hacker" onclick="addUser()" style="margin-top:10px;">CREATE USER</button></div>'; document.getElementById('usersList').innerHTML=h;}); }
function addUser(){ let u=document.getElementById('newUser').value, p=document.getElementById('newPass').value, r=document.getElementById('newRole').value, l=document.getElementById('newLimit').value; if(!u||!p){showMsg('Username and password required!','error');return;} callAPI('add_user',{username:u,password:p,role:r,limit:l},()=>{showMsg('User created!','success'); loadUsers(); document.getElementById('newUser').value=''; document.getElementById('newPass').value='';}); }
function deleteUser(id){ if(confirm('Delete this user?')) callAPI('delete_user',{id:id},()=>{loadUsers();}); }
function updateUserLimit(id){ let l=document.getElementById(`limit_${id}`).value; callAPI('update_user_limit',{id:id,limit:l},()=>{showMsg('Limit updated','success');}); }
function resetUser(id){ callAPI('reset_user',{id:id},()=>{loadUsers();}); }
function loadAllServices(){ callAPI('get_all_services',{},d=>{let h='<table class="data-table"><thead><tr><th>Service Name</th><th>API ID</th><th>Min/Max</th><th>Status</th><th>Action</th></tr></thead><tbody>'; d.services.forEach(s=>{h+=`<tr><td>${s.name}</td><td><input type="text" id="api_${s.id}" value="${s.api_id}" class="hacker-input" style="width:150px;"></td><td><input type="number" id="min_${s.id}" value="${s.min_order}" style="width:60px;background:#000;border:1px solid #0f0;color:#0f0;">/<input type="number" id="max_${s.id}" value="${s.max_order}" style="width:80px;background:#000;border:1px solid #0f0;color:#0f0;"></td><td><input type="checkbox" id="en_${s.id}" ${s.enabled?'checked':''}></td><td><button class="btn-hacker" onclick="updateService(${s.id})">Update</button></td></tr>`;}); h+='</tbody></table>'; document.getElementById('servicesList').innerHTML=h;}); }
function updateService(id){ let api=document.getElementById(`api_${id}`).value, en=document.getElementById(`en_${id}`).checked?1:0, min=document.getElementById(`min_${id}`).value, max=document.getElementById(`max_${id}`).value; callAPI('update_service',{id:id,api_id:api,enabled:en,min_order:min,max_order:max},()=>{showMsg('Service updated!','success');}); }
function testAPI(){ callAPI('test_api',{},d=>{showMsg('API Response: '+JSON.stringify(d.response),'success');}); }
function loadSchedule(){ callAPI('get_schedule',{},d=>{let h=''; for(let i=0;i<=12;i++){let v=d[`hour_${i}`]||(100+i*20); h+=`<div class="schedule-item"><div>Hour ${i.toString().padStart(2,'0')}</div><input type="number" id="hour_${i}" value="${v}"></div>`;} document.getElementById('scheduleGrid').innerHTML=h;}); }
function saveSchedule(){ let s={}; for(let i=0;i<=12;i++) s[`hour_${i}`]=document.getElementById(`hour_${i}`).value; callAPI('save_schedule',s,()=>{showMsg('Schedule saved!','success');}); }
function loadAllOrders(){ callAPI('get_all_orders',{},d=>{if(d.orders?.length){let h='<table class="data-table"><thead><tr><th>Order ID</th><th>User</th><th>Service</th><th>Quantity</th><th>Status</th><th>Date</th></tr></thead><tbody>'; d.orders.forEach(o=>{let badgeClass=o.status==='completed'?'badge-completed':(o.status==='processing'?'badge-processing':'badge-pending'); h+=`<tr><td>${o.order_id}</td><td>${o.username}</td><td>${o.service_name}</td><td>${o.quantity}</td><td><span class="badge ${badgeClass}">${o.status}</span></td><td>${o.created_at?.substring(0,16)}</td></tr>`;}); h+='</tbody></table>'; document.getElementById('allOrdersList').innerHTML=h;}else{document.getElementById('allOrdersList').innerHTML='<p>No orders yet</p>';}}); }
setInterval(()=>{if(currentUser){loadUserOrders(); if(currentUser.role==='admin'){loadAllOrders();loadStats();}}},30000);
</script>
</body>
</html>
'''

# ==================== ROUTES ====================
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        action = request.form.get('action')
        
        # LOGIN
        if action == 'login':
            username = request.form.get('username')
            password = hashlib.md5(request.form.get('password', '').encode()).hexdigest()
            user = User.query.filter_by(username=username, password=password).first()
            if user:
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                session['name'] = user.name
                return jsonify({'success': True, 'role': user.role})
            return jsonify({'success': False})
        
        # LOGOUT
        if action == 'logout':
            session.clear()
            return jsonify({'success': True})
        
        # GET USER
        if action == 'get_user':
            if 'user_id' not in session:
                return jsonify({'success': False})
            user = User.query.get(session['user_id'])
            return jsonify({'success': True, 'user': {
                'name': user.name, 'role': user.role, 'daily_limit': user.daily_limit, 'orders_today': user.orders_today
            }})
        
        # GET SERVICES
        if action == 'get_services':
            services = Service.query.filter_by(enabled=True).all()
            return jsonify({'services': [{'id': s.id, 'name': s.name, 'min_order': s.min_order, 'max_order': s.max_order} for s in services]})
        
        # PLACE ORDER
        if action == 'place_order':
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'Not logged in'})
            
            service_id = request.form.get('service_id')
            url = request.form.get('url')
            qty = int(request.form.get('quantity', 0))
            uid = session['user_id']
            
            service = Service.query.get(service_id)
            if not service or not service.enabled:
                return jsonify({'success': False, 'message': 'Service not available'})
            
            user = User.query.get(uid)
            if user.daily_limit > 0 and user.orders_today >= user.daily_limit:
                return jsonify({'success': False, 'message': f'Daily limit reached! Max {user.daily_limit} orders/day'})
            
            if qty < service.min_order or qty > service.max_order:
                return jsonify({'success': False, 'message': f'Quantity must be between {service.min_order} and {service.max_order}'})
            
            result = call_yoyomedia_api(service.api_id, url, qty)
            
            order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uid}"
            api_order_id = result.get('order', '')
            status = 'processing' if api_order_id else 'pending'
            
            order = Order(order_id=order_id, user_id=uid, service_id=service_id, url=url, quantity=qty, api_order_id=api_order_id, status=status)
            db.session.add(order)
            user.orders_today += 1
            db.session.commit()
            
            return jsonify({'success': True, 'order_id': order_id})
        
        # GET USER ORDERS
        if action == 'get_orders':
            if 'user_id' not in session:
                return jsonify({'success': False})
            orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).limit(10).all()
            return jsonify({'orders': [{
                'order_id': o.order_id, 'service_name': Service.query.get(o.service_id).name if Service.query.get(o.service_id) else 'Unknown',
                'quantity': o.quantity, 'status': o.status, 'created_at': o.created_at.isoformat()
            } for o in orders]})
        
        # ==================== ADMIN ONLY ====================
        if session.get('role') != 'admin':
            return jsonify({'success': False})
        
        # GET STATS
        if action == 'get_stats':
            return jsonify({
                'total_users': User.query.count(),
                'total_orders': Order.query.count(),
                'active_orders': Order.query.filter(Order.status.in_(['pending', 'processing'])).count(),
                'today_orders': Order.query.filter(db.func.date(Order.created_at) == date.today()).count()
            })
        
        # GET USERS
        if action == 'get_users':
            users = User.query.all()
            return jsonify({'users': [{'id': u.id, 'username': u.username, 'role': u.role, 'daily_limit': u.daily_limit, 'orders_today': u.orders_today} for u in users]})
        
        # ADD USER
        if action == 'add_user':
            u = request.form.get('username')
            p = hashlib.md5(request.form.get('password', '').encode()).hexdigest()
            r = request.form.get('role')
            l = request.form.get('limit')
            user = User(username=u, password=p, role=r, name=u, daily_limit=l)
            db.session.add(user)
            db.session.commit()
            return jsonify({'success': True})
        
        # DELETE USER
        if action == 'delete_user':
            uid = request.form.get('id')
            user = User.query.get(uid)
            if user and user.username != 'admin':
                db.session.delete(user)
                db.session.commit()
            return jsonify({'success': True})
        
        # UPDATE USER LIMIT
        if action == 'update_user_limit':
            uid = request.form.get('id')
            limit = request.form.get('limit')
            user = User.query.get(uid)
            if user:
                user.daily_limit = limit
                db.session.commit()
            return jsonify({'success': True})
        
        # RESET USER
        if action == 'reset_user':
            uid = request.form.get('id')
            user = User.query.get(uid)
            if user:
                user.orders_today = 0
                db.session.commit()
            return jsonify({'success': True})
        
        # GET ALL SERVICES
        if action == 'get_all_services':
            services = Service.query.all()
            return jsonify({'services': [{'id': s.id, 'name': s.name, 'api_id': s.api_id, 'min_order': s.min_order, 'max_order': s.max_order, 'enabled': s.enabled} for s in services]})
        
        # UPDATE SERVICE
        if action == 'update_service':
            sid = request.form.get('id')
            api = request.form.get('api_id')
            en = request.form.get('enabled')
            min_o = request.form.get('min_order')
            max_o = request.form.get('max_order')
            service = Service.query.get(sid)
            if service:
                service.api_id = api
                service.enabled = bool(int(en))
                service.min_order = min_o
                service.max_order = max_o
                db.session.commit()
            return jsonify({'success': True})
        
        # GET SCHEDULE
        if action == 'get_schedule':
            schedule = Schedule.query.first()
            if schedule:
                return jsonify({f'hour_{i}': getattr(schedule, f'hour_{i}', 100+(i*20)) for i in range(13)})
            return jsonify({})
        
        # SAVE SCHEDULE
        if action == 'save_schedule':
            schedule = Schedule.query.first()
            if not schedule:
                schedule = Schedule()
                db.session.add(schedule)
            for i in range(13):
                setattr(schedule, f'hour_{i}', int(request.form.get(f'hour_{i}', 100+(i*20))))
            schedule.updated_at = datetime.now()
            db.session.commit()
            return jsonify({'success': True})
        
        # GET ALL ORDERS
        if action == 'get_all_orders':
            orders = Order.query.order_by(Order.created_at.desc()).limit(50).all()
            return jsonify({'orders': [{
                'order_id': o.order_id, 'username': User.query.get(o.user_id).username if User.query.get(o.user_id) else 'Unknown',
                'service_name': Service.query.get(o.service_id).name if Service.query.get(o.service_id) else 'Unknown',
                'quantity': o.quantity, 'status': o.status, 'created_at': o.created_at.isoformat()
            } for o in orders]})
        
        # TEST API
        if action == 'test_api':
            result = call_yoyomedia_api(LIKES_ID, 'https://instagram.com/test', 10)
            return jsonify({'response': result})
        
        return jsonify({'error': 'Invalid action'})
    
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)