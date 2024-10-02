from flask import Flask, render_template, request, redirect, url_for, session
import os
import subprocess
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure random key

# Setup the SQLite database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database model for Users
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)

# Function to list available Wi-Fi networks
def list_wifi_networks():
    try:
        output = subprocess.check_output(['netsh', 'wlan', 'show', 'network', 'mode=Bssid'])
        networks = []
        lines = output.decode().split('\n')
        for line in lines:
            if 'SSID' in line:
                ssid = line.split(':')[1].strip()
                if ssid not in networks:
                    networks.append(ssid)
        return networks
    except Exception as e:
        print(f"Error fetching networks: {e}")
        return []

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid Username or Password"
            return render_template('login.html', error=error)
    
    return render_template('login.html')

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password == confirm_password:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                return render_template('create_account.html', error="User already exists")
            
            new_user = User(first_name=first_name, last_name=last_name, username=username, password=password)
            db.session.add(new_user)
            db.session.commit()

            return render_template('create_account.html', success=True)
        else:
            return render_template('create_account.html', error="Passwords do not match")

    return render_template('create_account.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    wifi_networks = list_wifi_networks()
    connection_status = None
    connected_ssid = None
    connection_error = None
    video_url = None

    # Add the IP address of the ESP32-CAM here
    camera_ip = "192.168.243.232"  # Replace with your actual ESP32-CAM IP address
    video_url = f"http://{camera_ip}:81/stream"  # Update this according to your stream URL

    if request.method == 'POST':
        if 'refresh' in request.form:  # Handle refresh button
            wifi_networks = list_wifi_networks()
        else:
            ssid = request.form.get('ssid')
            password = request.form.get('password')
        
            if ssid and password:
                if connect_to_wifi(ssid, password):
                    connection_status = True
                    connected_ssid = ssid
                else:
                    connection_error = True

    return render_template('dashboard.html', 
                           wifi_networks=wifi_networks,
                           connection_status=connection_status,
                           connected_ssid=connected_ssid,
                           connection_error=connection_error,
                           video_url=video_url)

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_info = User.query.filter_by(username=session['username']).first()
    return render_template('profile.html', user_info=user_info)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# Function to connect to Wi-Fi
def connect_to_wifi(ssid, password):
    try:
        profile_name = ssid
        profile_xml = f"""
        <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
            <name>{profile_name}</name>
            <SSIDConfig>
                <SSID>
                    <name>{profile_name}</name>
                </SSID>
            </SSIDConfig>
            <connectionType>ESS</connectionType>
            <connectionMode>auto</connectionMode>
            <MSM>
                <security>
                    <authEncryption>
                        <authentication>WPA2PSK</authentication>
                        <encryption>AES</encryption>
                        <useOneX>false</useOneX>
                    </authEncryption>
                    <sharedKey>
                        <keyType>passPhrase</keyType>
                        <protected>false</protected>
                        <keyMaterial>{password}</keyMaterial>
                    </sharedKey>
                </security>
            </MSM>
        </WLANProfile>
        """
        profile_path = 'wifi_profile.xml'
        with open(profile_path, 'w') as file:
            file.write(profile_xml)

        subprocess.check_call(['netsh', 'wlan', 'add', 'profile', f'filename={profile_path}'])

        command = f'netsh wlan connect name="{profile_name}"'
        subprocess.check_call(command, shell=True)
        return True
    except subprocess.CalledProcessError:
        return False

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(host='0.0.0.0', port=8000, debug=True)
