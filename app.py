
from flask import Flask, render_template_string, request
import pandas as pd
import os

app = Flask(__name__)

# تحميل البيانات من ملف Excel
sheet1_df = pd.read_excel("data.xlsx", sheet_name="Sheet1")

# HTML Template
html_template = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>نتيجة الطالب</title>
    <style>
        body { font-family: 'Arial'; background-color: #f0f0f0; text-align: center; }
        .container { margin: 40px auto; width: 70%; }
        table { border-collapse: collapse; margin: auto; width: 100%; font-size: 18px; direction: rtl; background-color: #fff; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: center; }
        th { width: 40%; }
        td { width: 60%; }
        .title { background-color: orange; font-weight: bold; font-size: 20px; }
        .footer { background-color: #a0d080; font-style: italic; }
        .first-year { background-color: #e0f7fa; }
        .second-year { background-color: #fff3e0; }
        .third-year { background-color: #ede7f6; }
        .imsurgery { background-color: #d0e0ff; }
        .totals { background-color: #d0f8ce; }
        .rank { background-color: #ffe0f0; }
        input[type="text"] {
            font-size: 20px;
            padding: 12px 20px;
            width: 300px;
        }
        input[type="submit"] {
            font-size: 18px;
            padding: 12px 20px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <form method="POST">
            <label class="title">ادخل رقم الطالب:</label><br>
            <input type="text" name="student_id" required>
            <input type="submit" value="بحث">
        </form>
        {% if result %}
        <table>
            <tr><td colspan="2" class="title">اسم الطالب: {{ result['NAME'] }}</td></tr>
            <tr><th class="title">الدرجة</th><th class="title">البند</th></tr>
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
            <tr class="footer"><td colspan="2">Designed by Abdo Hamdy Aly</td></tr>
        </table>
        {% elif searched %}
            <p>لم يتم العثور على الطالب.</p>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def search():
    result = None
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
    return render_template_string(html_template, result=result, searched=searched)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
