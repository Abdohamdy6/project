from flask import Flask, render_template_string, request
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)

sheet1_df = pd.read_excel("data.xlsx", sheet_name="Sheet1")
sheet2_df = pd.read_excel("data.xlsx", sheet_name="Sheet2")

html_template = """ 
<!doctype html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>AFM 26 RESULTS</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logoTB.png') }}">
    <style>
        body {
            font-family: 'Arial', sans-serif;
            background-color: #f0f4f8;
            text-align: center;
            position: relative;
        }
        body::before {
            content: "";
            background-image: url('https://i.ibb.co/zHRhsP6j');
            background-size: cover;
            background-position: center;
            opacity: 0.1;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            position: fixed;
            z-index: -1;
        }
        .container {
            margin: 60px auto;
            width: 70%;
            background-color: rgba(255, 255, 255, 0.9);
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 0 15px rgba(0,0,0,0.1);
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
            margin-bottom: 30px;
            direction: ltr;
        }
        .header img {
            height: 70px;
            width: auto;
            opacity: 0.85;
        }
        .header-text {
            text-align: left;
            direction: ltr;
        }
        .header-text h1 {
            font-size: 36px;
            margin: 0;
            font-weight: 900;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
            letter-spacing: 1px;
            font-family: 'Arial Black', sans-serif;
        }
        .header-text h1 a {
            text-decoration: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header-text p {
            font-size: 18px;
            margin: 5px 0 0 0;
            font-style: italic;
            font-weight: bold;
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
        }
        .header-text p a {
            text-decoration: none;
            font-style: italic;
            font-weight: bold;
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        /* Navigation Buttons */
        .nav-buttons {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        
        .nav-btn {
            padding: 15px 30px;
            font-size: 18px;
            font-weight: bold;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            color: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .nav-btn.search {
            background: linear-gradient(45deg, #4285f4, #34a853);
        }
        
        .nav-btn.distance {
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
        }
        
        .nav-btn.need {
            background: linear-gradient(45deg, #9c27b0, #e91e63);
        }
        
        .nav-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        
        .nav-btn.active {
            background: linear-gradient(45deg, #333, #555);
        }
        
        table {
            border-collapse: collapse;
            margin: auto;
            width: 100%;
            font-size: 18px;
            direction: rtl;
            background-color: #fff;
        }
        th, td {
            border: 1px solid #ccc;
            padding: 10px;
            text-align: center;
        }
        th { width: 40%; }
        td { width: 60%; font-weight: bold; }
        .title {
            font-weight: bold;
            font-size: 20px;
            background-color: #b3e5fc;
            color: #000;
        }
        .footer {
            background-color: #a0d080;
            font-style: italic;
        }
        .first-year { background-color: #e0f7fa; }
        .second-year { background-color: #fff3e0; }
        .third-year { background-color: #ede7f6; }
        .fourth-year { background-color: #d0e0ff; }
        .totals { background-color: #d0f8ce; }
        .rank { background-color: #ffe0f0; }
        
        form {
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        label.title {
            font-size: 36px;
            font-weight: 800;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 25px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
            letter-spacing: 2px;
            text-transform: uppercase;
            font-family: 'Arial Black', sans-serif;
        }
        
        /* Interactive Search Box Styles */
        .search-container {
            position: relative;
            margin: 20px 0;
        }
        
        input[type="text"], input[type="number"] {
            font-size: 24px;
            padding: 15px 25px;
            width: 400px;
            border: 2px solid #ddd;
            border-radius: 25px;
            transition: all 0.3s ease;
            outline: none;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        input[type="text"]:focus, input[type="number"]:focus {
            border-color: #4285f4;
            box-shadow: 0 0 15px rgba(66, 133, 244, 0.3);
            transform: scale(1.02);
        }
        
        input[type="submit"] {
            font-size: 20px;
            padding: 12px 30px;
            margin-top: 15px;
            border-radius: 25px;
            background: linear-gradient(45deg, #4285f4, #34a853);
            color: white;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(66, 133, 244, 0.3);
        }
        
        input[type="submit"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(66, 133, 244, 0.4);
        }
        
        input[type="submit"]:active {
            transform: translateY(0);
            box-shadow: 0 2px 10px rgba(66, 133, 244, 0.3);
        }
        
        p {
            font-size: 22px;
            color: red;
        }
        
        /* Distance Result Styles */
        .distance-result {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 20px;
            margin: 30px 0;
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }
        
        .distance-result h2 {
            font-size: 32px;
            margin-bottom: 20px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        /* Arrow Progress Styles - Modified for correct direction */
        .progress-arrow-container {
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 30px 0;
            position: relative;
            direction: ltr; /* Force LTR direction for arrow layout */
        }
        
        .progress-circle {
            width: 140px;
            height: 140px;
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
            position: relative;
            z-index: 2;
        }
        
        .current-circle {
            background: linear-gradient(135deg, #ff6b6b, #ee5a52);
            box-shadow: 0 8px 20px rgba(255, 107, 107, 0.4);
        }
        
        .target-circle {
            background: linear-gradient(135deg, #4ecdc4, #44a08d);
            box-shadow: 0 8px 20px rgba(78, 205, 196, 0.4);
        }
        
        .circle-label {
            font-size: 16px;
            margin-bottom: 5px;
            opacity: 0.9;
        }
        
        .circle-value {
            font-size: 26px;
            font-weight: 900;
        }
        
        .progress-arrow {
            flex: 0 0 200px; /* Made arrow even longer */
            height: 12px;
            background: linear-gradient(90deg, #ff6b6b, #4ecdc4);
            margin: 0 25px;
            border-radius: 6px;
            position: relative;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .progress-arrow::after {
            content: '';
            position: absolute;
            right: -18px; /* Adjusted for longer arrow */
            top: 50%;
            transform: translateY(-50%);
            width: 0;
            height: 0;
            border-left: 22px solid #4ecdc4;
            border-top: 20px solid transparent;
            border-bottom: 20px solid transparent;
            filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.3));
        }
        
        .progress-difference {
            position: absolute;
            top: -50px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(255,255,255,0.95);
            color: #333;
            padding: 12px 20px;
            border-radius: 25px;
            font-size: 18px;
            font-weight: bold;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            z-index: 3;
            white-space: nowrap;
            min-width: 120px;
            text-align: center;
        }
        
        .progress-difference.positive {
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
        }
        
        .progress-difference.negative {
            background: linear-gradient(135deg, #f44336, #e53935);
            color: white;
        }
        
        .progress-difference.neutral {
            background: linear-gradient(135deg, #2196F3, #1976D2);
            color: white;
        }
        
        .motivational-message {
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            color: white;
            padding: 25px;
            border-radius: 15px;
            margin: 20px 0;
            font-size: 28px;
            font-weight: bold;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
            line-height: 1.4;
        }
        
        .motivational-message .highlight-number {
            font-size: 36px;
            text-decoration: underline;
            font-weight: 900;
        }
        
        /* Chart Titles with Icons */
        .chart-title {
            font-size: 26px;
            font-weight: bold;
            color: #2c3e50;
            margin: 30px 0 20px 0;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        }
        
        /* Animated Percentile Box */
        .percentile-box {
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4);
            background-size: 400% 400%;
            animation: gradientShift 3s ease infinite;
            color: white;
            font-size: 22px;
            font-weight: bold;
            padding: 20px;
            margin: 20px auto;
            border-radius: 20px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
            border: 3px solid white;
            max-width: 500px;
            position: relative;
            overflow: hidden;
        }
        
        .percentile-box::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent);
            transform: rotate(45deg);
            animation: shine 2s infinite;
        }
        
        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        @keyframes shine {
            0% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
            100% { transform: translateX(100%) translateY(100%) rotate(45deg); }
        }
        
        .free-palestine {
            margin-top: 40px;
            padding: 25px;
            font-size: 24px;
            font-weight: bold;
            color: white;
            background: linear-gradient(90deg, black 25%, white 25% 50%, green 50% 75%, red 75% 100%);
            border-radius: 12px;
            text-shadow: 1px 1px 2px #000;
        }

        .dual-input {
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
            justify-content: center;
            direction: ltr;
        }

        .dual-input input {
            width: 180px;
        }

        .dual-input label {
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://i.postimg.cc/0rHzBdbx/8.jpg" alt="Logo">
            <div class="header-text">
                <h1><a href="/">AFM 26 Results &amp; Analysis</a></h1>
                <p><a href="https://t.me/Abdo_Hamdi6" target="_blank">By : Abdo Hamdy Aly</a></p>
            </div>
        </div>

        <!-- Navigation Buttons -->
        <div class="nav-buttons">
            <a href="/?mode=search" class="nav-btn search {{ 'active' if mode == 'search' or not mode else '' }}">
                🔍 Student Search
            </a>
            <a href="/?mode=distance" class="nav-btn distance {{ 'active' if mode == 'distance' else '' }}">
                📏 How Far I am
            </a>
            <a href="/?mode=need" class="nav-btn need {{ 'active' if mode == 'need' else '' }}">
                🎯 How Much I Need
            </a>
        </div>

        {% if mode == 'need' %}
        <!-- Need Mode -->
        <form method="POST" action="/?mode=need">
            <label class="title">HOW MUCH I NEED</label><br>
            <div class="search-container">
                <div class="dual-input">
                    <div>
                        <label>Student ID</label>
                        <input type="text" name="student_id" placeholder="Enter your ID" required>
                    </div>
                    <div>
                        <label>Target Total %</label>
                        <input type="number" name="target_percentage" step="0.01" min="0" max="100" placeholder="Target %" required>
                    </div>
                </div>
                <br>
                <input type="submit" value="🧮 Calculate Required">
            </div>
        </form>

        {% if need_result %}
        <div class="distance-result">
            <h2>🎯 Required 5th Year Analysis</h2>
            <h3 style="font-size: 30px; margin: 15px 0; color: #ffeb3b; text-shadow: 2px 2px 4px rgba(0,0,0,0.5);">{{ need_result['student_name'] }}</h3>
            
            <div class="progress-arrow-container">
                <div class="progress-circle current-circle">
                    <div class="circle-label">Current</div>
                    <div class="circle-value">{{ need_result['current_percentage'] }}%</div>
                </div>
                
                <div class="progress-arrow">
                    <div class="progress-difference {% if need_result['required_5th_year_percentage'] > 0 and need_result['required_5th_year_percentage'] <= 100 %}positive{% elif need_result['required_5th_year_percentage'] > 100 %}negative{% else %}neutral{% endif %}">
                        {% if need_result['required_5th_year_percentage'] > 100 %}
                            Need >100%
                        {% elif need_result['required_5th_year_percentage'] < 0 %}
                            Target Achieved!
                        {% else %}
                            Need {{ need_result['required_5th_year_percentage'] }}%
                        {% endif %}
                    </div>
                </div>
                
                <div class="progress-circle target-circle">
                    <div class="circle-label">Target</div>
                    <div class="circle-value">{{ need_result['target_percentage'] }}%</div>
                </div>
            </div>
            
            {% if need_result['required_5th_year_percentage'] < 60 %}
                <div class="motivational-message" style="background: linear-gradient(45deg, #f44336, #ff5722);">
                    ❌ Target requires <span class="highlight-number">{{ need_result['required_5th_year_score'] }}</span> points (<span class="highlight-number">{{ need_result['required_5th_year_percentage'] }}%</span>) in 5th year, which is below 60%!
                    <br><br>This is impossible! Minimum passing grade for 5th year is 60%. Please set a more realistic target! 🎯
                </div>
            {% elif need_result['required_5th_year_percentage'] <= 100 and need_result['required_5th_year_percentage'] >= 60 %}
                <div class="motivational-message">
                    🎯 You need to score <span class="highlight-number">{{ need_result['required_5th_year_score'] }}</span> points (<span class="highlight-number">{{ need_result['required_5th_year_percentage'] }}%</span>) in your 5th year to reach {{ need_result['target_percentage'] }}% total!
                    <br><br>{% if need_result['required_5th_year_percentage'] <= 70 %}Easy target! 💪{% elif need_result['required_5th_year_percentage'] <= 80 %}Good target! Keep working! 📚{% elif need_result['required_5th_year_percentage'] <= 90 %}Challenging but achievable! 🔥{% else %}Very challenging! Give your best! 🚀{% endif %}
                </div>
            {% elif need_result['required_5th_year_percentage'] > 100 %}
                <div class="motivational-message" style="background: linear-gradient(45deg, #f44336, #ff5722);">
                    ⚠️ Target requires <span class="highlight-number">{{ need_result['required_5th_year_score'] }}</span> points (<span class="highlight-number">{{ need_result['required_5th_year_percentage'] }}%</span>) in 5th year, which is above 100%!
                    <br><br>Consider a more realistic target! 🎯
                </div>
            {% else %}
                <div class="motivational-message" style="background: linear-gradient(45deg, #4CAF50, #45a049);">
                    🎉 You've already exceeded your target of {{ need_result['target_percentage'] }}%!
                    <br><br>Congratulations! Set a higher goal! 🏆
                </div>
            {% endif %}
        </div>

        {% elif need_searched %}
            <p>❌ Student not found or invalid target percentage</p>
        {% endif %}

        {% elif mode == 'distance' %}
        <!-- Distance Mode -->
        <form method="POST" action="/?mode=distance">
            <label class="title">HOW FAR I AM</label><br>
            <div class="search-container">
                <div class="dual-input">
                    <div>
                        <label>Student ID</label>
                        <input type="text" name="student_id" placeholder="Enter your ID" required>
                    </div>
                    <div>
                        <label>Target Rank</label>
                        <input type="number" name="target_rank" min="1" placeholder="Target rank" required>
                    </div>
                </div>
                <br>
                <input type="submit" value="🎯 Calculate Distance">
            </div>
        </form>

        {% if distance_result %}
        <div class="distance-result">
            <h2>📊 Distance Analysis</h2>
            <h3 style="font-size: 30px; margin: 15px 0; color: #ffeb3b; text-shadow: 2px 2px 4px rgba(0,0,0,0.5);">{{ distance_result['student_name'] }}</h3>
            
            <div class="progress-arrow-container">
                <div class="progress-circle current-circle">
                    <div class="circle-label">Current</div>
                    <div class="circle-value">#{{ distance_result['current_rank'] }}</div>
                </div>
                
                <div class="progress-arrow">
                    <div class="progress-difference {% if distance_result['points_needed'] > 0 %}positive{% elif distance_result['points_needed'] == 0 %}neutral{% else %}negative{% endif %}">
                        {% if distance_result['points_needed'] > 0 %}
                            +{{ distance_result['points_needed'] }} Points
                        {% elif distance_result['points_needed'] == 0 %}
                            At Target!
                        {% else %}
                            {{ distance_result['points_needed']|abs }} Points Ahead
                        {% endif %}
                    </div>
                </div>
                
                <div class="progress-circle target-circle">
                    <div class="circle-label">Target</div>
                    <div class="circle-value">#{{ distance_result['target_rank'] }}</div>
                </div>
            </div>
            
            {% if distance_result['points_needed'] > 0 %}
                <div class="motivational-message">
                    🚀 You need <span class="highlight-number">{{ distance_result['points_needed'] }}</span> more points to reach rank #{{ distance_result['target_rank'] }}!
                    <br><br>Keep pushing forward! 💪
                </div>
            {% elif distance_result['points_needed'] == 0 %}
                <div class="motivational-message" style="background: linear-gradient(45deg, #4CAF50, #45a049);">
                    🎉 Congratulations! You're already at or above rank #{{ distance_result['target_rank'] }}! 
                    <br><br>Amazing job! 🏆
                </div>
            {% else %}
                <div class="motivational-message" style="background: linear-gradient(45deg, #4CAF50, #45a049);">
                    🌟 You're already <span class="highlight-number">{{ distance_result['points_needed']|abs }}</span> points ahead of rank #{{ distance_result['target_rank'] }}!
                    <br><br>You're doing great! Keep it up! 🔥
                </div>
            {% endif %}
        </div>

        {% elif distance_searched %}
            <p>❌ Student not found or invalid target rank</p>
        {% endif %}

        {% else %}
        <!-- Search Mode (Default) -->
        <form method="POST" action="/?mode=search">
            <label class="title">ENTER ID</label><br>
            <div class="search-container">
                <input type="text" name="student_id" required>
                <br>
                <input type="submit" value="🔍 Search">
            </div>
        </form>
        
        {% if result %}
        <table>
            <tr><td colspan="2" class="title">👨‍🎓 اسم الطالب : {{ result['NAME'] }}</td></tr>
            <tr><th class="title">🔢 MARK</th><th class="title">📚 SUBJECT</th></tr>
            {% for key, value in result.items() %}
                {% if key != 'ID' and key != 'NAME' %}
                    {% set key_upper = key.upper().strip() %}
                    {% if key_upper in ['FIRST YEAR', 'LONG FIRST YEAR', 'RESEARCH STEP I', 'COMMUNICATION STEP I', 'PROFESSIONALISM STEP I'] %}
                        {% set css_class = 'first-year' %}
                    {% elif key_upper in ['SECOND YEAR', 'LONG SECOND YEAR', 'RESEARCH STEP II', 'COMMUNICATION STEP II', 'PROFESSIONALISM STEP II'] %}
                        {% set css_class = 'second-year' %}
                    {% elif key_upper in ['THIRD YEAR', 'LONG THIRD YEAR', 'RESEARCH STEP III', 'COMMUNICATION STEP III', 'PROFESSIONALISM STEP III'] %}
                        {% set css_class = 'third-year' %}
                    {% elif key_upper in ['FOURTH YEAR', 'LONG FOURTH YEAR', 'RESEARCH STEP IIII', 'COMMUNICATION STEP IIII', 'PROFESSIONALISM STEP IIII'] %}
                        {% set css_class = 'fourth-year' %}
                    {% elif key_upper in ['TOTAL', 'TOTAL RANK', '%', 'PERCENTAGE'] %}
                        {% set css_class = 'totals' %}
                    {% elif 'RANK' in key_upper %}
                        {% set css_class = 'rank' %}
                    {% else %}
                        {% set css_class = '' %}
                    {% endif %}
                    <tr class="{{ css_class }}"><td>{{ value }}</td><td>{{ key }}</td></tr>
                {% endif %}
            {% endfor %}
            <tr class="footer"><td colspan="2">💻 Designed and Coded By : Abdo Hamdy Aly</td></tr>
            <tr>
                <td colspan="2" style="text-align: center; font-size: 18px; padding: 15px;">
                    <a href="https://t.me/Abdo_Hamdi6" target="_blank" style="text-decoration: none; color: black;">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/8/82/Telegram_logo.svg" alt="Telegram" style="width: 24px; vertical-align: middle; margin-left: 8px;">
                        📱 @Abdo_Hamdi6
                    </a>
                </td>
            </tr>
        </table>

        {% if plot_url %}
            <div class="chart-title">📈 Student Score Distribution</div>
            <img src="data:image/png;base64,{{ plot_url }}">
            {% if percentile %}
                <div class="percentile-box">
                    🎯 YOU ARE IN THE {{ percentile }}th PERCENTILE! 🏆
                </div>
            {% endif %}
        {% endif %}

        {% if rank_progress_url %}
            <div class="chart-title">📊 Cumulative Rank Progress</div>
            <img src="data:image/png;base64,{{ rank_progress_url }}">
        {% endif %}

        {% elif searched %}
            <p>❌ Student not found</p>
        {% endif %}
        {% endif %}

        <!-- شريط دعم فلسطين -->
        <div style="margin-top: 40px; padding: 20px 10px; border-radius: 12px;
                    background: linear-gradient(to right, black, white, green, red);
                    color: white; font-size: 24px; font-weight: bold; text-shadow: 1px 1px 2px black;">
            🇵🇸 FREE PALESTINE 🇵🇸
        </div>
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def main():
    mode = request.args.get('mode', 'search')
    result = None
    plot_url = None
    rank_progress_url = None
    percentile = None
    searched = False
    distance_result = None
    distance_searched = False
    need_result = None
    need_searched = False

    if request.method == 'POST':
        if mode == 'need':
            # Need calculation mode
            student_id = request.form.get('student_id')
            target_percentage = request.form.get('target_percentage')
            need_searched = True
            
            try:
                target_percentage = float(target_percentage)
                
                # Find student data
                student_match = sheet1_df[sheet1_df['ID'].astype(str) == student_id]
                
                if not student_match.empty:
                    student_data = student_match.iloc[0]
                    student_name = student_data.get('NAME')
                    
                    # Calculate current total from first 4 years (assuming TOTAL column contains total of all years so far)
                    current_total_score = student_data.get('TOTAL', 0)  # This should be the sum of first 4 years
                    
                    # Calculate current percentage based on 3630 (first 4 years only)
                    current_percentage = (current_total_score / 3630) * 100
                    
                    # Calculate required total score to reach target percentage
                    required_total_score = (target_percentage / 100) * 4875
                    
                    # Calculate required 5th year score
                    required_5th_year_score = required_total_score - current_total_score
                    
                    # Calculate required 5th year percentage (out of 1245)
                    required_5th_year_percentage = (required_5th_year_score / 1245) * 100
                    
                    need_result = {
                        'student_name': student_name,
                        'current_percentage': round(current_percentage, 2) if pd.notna(current_percentage) else 0,
                        'target_percentage': target_percentage,
                        'required_5th_year_score': round(required_5th_year_score, 2) if pd.notna(required_5th_year_score) else 0,
                        'required_5th_year_percentage': round(required_5th_year_percentage, 2) if pd.notna(required_5th_year_percentage) else 0
                    }
                    
            except (ValueError, TypeError):
                need_result = None
                
        elif mode == 'distance':
            # Distance calculation mode
            student_id = request.form.get('student_id')
            target_rank = request.form.get('target_rank')
            distance_searched = True
            
            try:
                target_rank = int(target_rank)
                
                # Find student data
                student_match = sheet1_df[sheet1_df['ID'].astype(str) == student_id]
                
                if not student_match.empty:
                    student_data = student_match.iloc[0]
                    current_score = student_data.get('TOTAL')
                    student_name = student_data.get('NAME')
                    
                    # Get current rank
                    current_rank = (sheet1_df['TOTAL'] > current_score).sum() + 1
                    
                    # Get target score (score of student at target rank)
                    sorted_scores = sheet1_df.sort_values('TOTAL', ascending=False)
                    
                    if target_rank <= len(sorted_scores):
                        target_score = sorted_scores.iloc[target_rank - 1]['TOTAL']
                        points_needed = target_score - current_score
                        
                        distance_result = {
                            'student_name': student_name,
                            'current_rank': current_rank,
                            'target_rank': target_rank,
                            'points_needed': round(points_needed, 2) if pd.notna(points_needed) else 0
                        }
                        
            except (ValueError, IndexError):
                distance_result = None
                
        else:
            # Original search mode
            student_id = request.form['student_id']
            searched = True
            match = sheet1_df[sheet1_df['ID'].astype(str) == student_id]
            if not match.empty:
                raw_result = match.iloc[0].to_dict()
                formatted_result = {}
                for key, val in raw_result.items():
                    if isinstance(val, float):
                        if '%' in key.upper() or key.strip().upper() in ['%', 'PERCENTAGE']:
                            if val <= 1:
                                formatted_result[key] = f"{round(val * 100, 2)}%"
                            else:
                                formatted_result[key] = f"{round(val, 2)}%"
                        elif val.is_integer():
                            formatted_result[key] = int(val)
                        else:
                            formatted_result[key] = round(val, 2)
                    else:
                        formatted_result[key] = val
                result = formatted_result

                total_scores = sheet1_df['TOTAL'].dropna()
                student_score = raw_result.get('TOTAL')

                if pd.notna(student_score):
                    percentile = round((total_scores < student_score).mean() * 100)
                    avg_score = total_scores.mean()

                    plt.figure(figsize=(8, 5))
                    plt.hist(total_scores, bins=20, color='#66b3ff', edgecolor='black')
                    plt.axvline(student_score, color='orange', linestyle='solid', linewidth=2,
                                label=f'Student Score: {student_score}')
                    plt.axvline(avg_score, color='black', linestyle='dashed', linewidth=2,
                                label='Class Average')

                    ymax = plt.gca().get_ylim()[1]
                    y_line = ymax * 0.7
                    plt.hlines(y_line, min(avg_score, student_score), max(avg_score, student_score),
                               colors='red', linestyles='dashed', linewidth=2)

                    diff_percent = round(abs(student_score - avg_score) / 3630 * 100, 1)
                    mid_x = (student_score + avg_score) / 2
                    plt.text(mid_x, y_line + ymax * 0.03, f'{diff_percent}%', fontsize=10, fontweight='bold', ha='center', color='red')

                    plt.plot([], [], 'r--', label='% above/below average')

                    plt.xlabel('Scores')
                    plt.ylabel('Number of Students')
                    plt.title('Score Distribution with Student Highlighted')
                    plt.legend()

                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')
                    buf.seek(0)
                    plot_url = base64.b64encode(buf.getvalue()).decode('utf8')
                    buf.close()
                    plt.close()

                rank_match = sheet2_df[sheet2_df['ID'].astype(str) == student_id]
                if not rank_match.empty:
                    rank_data = rank_match.iloc[0].to_dict()
                else:
                    rank_data = {}

                rank_columns = {
                    "FIRST YEAR RANK": ("FIRST YEAR", "#e0f7fa"),
                    "SECOND YEAR RANK C": ("SECOND YEAR", "#fff3e0"),
                    "THIRD YEAR RANK C": ("THIRD YEAR", "#ede7f6"),
                    "FOURTH YEAR RANK C": ("FOURTH YEAR", "#d0e0ff"),
                }

                progress_labels = []
                rank_values = []
                colors = []

                for col, (label, color) in rank_columns.items():
                    rank = rank_data.get(col)
                    if pd.notna(rank):
                        progress_labels.append(label)
                        rank_values.append(rank)
                        colors.append(color)

                if progress_labels and rank_values:
                    plt.figure(figsize=(8, 5))
                    plt.plot(progress_labels, rank_values, marker='o', linestyle='-', color='black', linewidth=2)

                    for i in range(len(progress_labels)):
                        plt.plot(progress_labels[i], rank_values[i], '3', markersize=10, color=colors[i])
                        plt.text(progress_labels[i], rank_values[i] + 0.5, f'{int(rank_values[i])}',
                                 ha='center', va='top', fontsize=14, fontweight='bold', color='black',
                                 bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='black'))

                        if i > 0:
                            change = rank_values[i - 1] - rank_values[i]
                            color = 'green' if change > 0 else 'red'
                            sign = '+' if change > 0 else ''
                            arrow = '⬆' if change > 0 else '⬇'

                            mid_x = (i - 0.5)
                            mid_y = (rank_values[i - 1] + rank_values[i]) / 2
                            below_line_y = mid_y + 2.5

                            plt.text(mid_x, below_line_y, f'{arrow} {sign}{abs(int(change))}',
                                     fontsize=11, fontweight='bold', color=color,
                                     ha='center', va='top',
                                     bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor=color))

                    plt.ylabel('Cumulative Rank')
                    plt.title('Cumulative Progress Based on Class Rank')
                    plt.gca().invert_yaxis()
                    plt.grid(True)

                    buf = io.BytesIO()
                    plt.savefig(buf, format='png')
                    buf.seek(0)
                    rank_progress_url = base64.b64encode(buf.getvalue()).decode('utf8')
                    buf.close()
                    plt.close()

    return render_template_string(html_template, 
                                  mode=mode,
                                  result=result, 
                                  plot_url=plot_url,
                                  rank_progress_url=rank_progress_url, 
                                  percentile=percentile, 
                                  searched=searched,
                                  distance_result=distance_result,
                                  distance_searched=distance_searched,
                                  need_result=need_result,
                                  need_searched=need_searched)

if __name__ == '__main__':
    app.run(debug=True)