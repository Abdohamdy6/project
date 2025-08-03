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
            font-weight: bold;
            color: #333;
        }
        .header-text h1 a {
            text-decoration: none;
            color: #333;
        }
        .header-text p {
            font-size: 18px;
            margin: 5px 0 0 0;
            font-style: italic;
            color: #555;
        }
        .header-text p a {
            text-decoration: none;
            color: #555;
            font-style: italic;
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
        .imsurgery { background-color: #d0e0ff; }
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
        
        input[type="text"] {
            font-size: 24px;
            padding: 15px 25px;
            width: 400px;
            border: 2px solid #ddd;
            border-radius: 25px;
            transition: all 0.3s ease;
            outline: none;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        input[type="text"]:focus {
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://i.ibb.co/PZgW04kw/logo.png" alt="Logo">
            <div class="header-text">
                <h1><a href="/">AFM 26 Results &amp; Analysis</a></h1>
                <p><a href="https://t.me/Abdo_Hamdi6" target="_blank">By : Abdo Hamdy Aly</a></p>
            </div>
        </div>

        <form method="POST">
            <label class="title">ENTER ID</label><br>
            <div class="search-container">
                <input type="text" name="student_id" required>
                <br>
                <input type="submit" value="🔎 Search">
            </div>
        </form>
        
        {% if result %}
        <table>
            <tr><td colspan="2" class="title">👨‍🎓 اسم الطالب : {{ result['NAME'] }}</td></tr>
            <tr><th class="title">📝 MARK</th><th class="title">📚 SUBJECT</th></tr>
            {% for key, value in result.items() %}
                {% if key != 'ID' and key != 'NAME' %}
                    {% set key_upper = key.upper().strip() %}
                    {% if key_upper in ['FIRST YEAR', 'LONG FIRST YEAR', 'RESEARCH STEP I', 'COMMUNICATION STEP I', 'PROFESSIONALISM STEP I'] %}
                        {% set css_class = 'first-year' %}
                    {% elif key_upper in ['SECOND YEAR', 'LONG SECOND YEAR', 'RESEARCH STEP II', 'COMMUNICATION STEP II', 'PROFESSIONALISM STEP II'] %}
                        {% set css_class = 'second-year' %}
                    {% elif key_upper in ['THIRD YEAR', 'LONG THIRD YEAR', 'RESEARCH STEP III', 'COMMUNICATION STEP III', 'PROFESSIONALISM STEP III'] %}
                        {% set css_class = 'third-year' %}
                    {% elif key_upper in ['IM&SURGERY', 'IM&SURGERY RANK'] %}
                        {% set css_class = 'imsurgery' %}
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
        <!-- شريط دعم فلسطين -->
        <div style="margin-top: 40px; padding: 20px 10px; border-radius: 12px;
                    background: linear-gradient(to right, black, white, green, red);
                    color: white; font-size: 24px; font-weight: bold; text-shadow: 1px 1px 2px black;">
            🇵🇸 FREE PALESTINE 🇵🇸

        {% elif searched %}
            <p>❌ Student not found</p>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def search():
    result = None
    plot_url = None
    rank_progress_url = None
    percentile = None
    searched = False

    if request.method == 'POST':
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

                diff_percent = round(abs(student_score - avg_score) / 3180 * 100, 1)
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
                "TOTAL RANK": ("IM&SURGERY", "#d0e0ff"),
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

    return render_template_string(html_template, result=result, plot_url=plot_url,
                                  rank_progress_url=rank_progress_url, percentile=percentile, searched=searched)

if __name__ == '__main__':
    app.run(debug=True)