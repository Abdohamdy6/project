# AFM26 Results & Analysis Web App

A Flask-based web application that displays AFM26 student results and analysis with tables, graphs, and a downloadable PDF version — including a **“Free Palestine”** banner at the bottom.

---

## 📖 Overview
This project provides a simple and interactive way to visualize student performance data.  
Users can upload Excel files containing results, view detailed statistics in tables and charts, and export the full page (with formatting) as a PDF.  
The app is deployed on **Vercel** for easy online access.

---

## ⚙️ Features
- Upload and display student result data from Excel files (`data.xlsx`, `24.xlsx`, `25.xlsx`, etc.)
- Show results in well-formatted tables
- Visualize progress through percentile and rank charts
- Export the entire webpage (tables, charts, and banner) as a **PDF**
- Includes a **Free Palestine** banner with themed background at the bottom of the page
- Deployed using **Vercel**

---

## 🧩 Tech Stack
- **Python 3.x**
- **Flask**
- **HTML / CSS / JavaScript**
- **pandas** for data analysis
- **matplotlib / chart.js** for charts and visualizations
- **html2canvas** + **jsPDF** for PDF generation
- **Vercel** for deployment

---

## 🚀 How to Run Locally

1. **Clone the repository**
   ```bash
   git clone https://github.com/Abdohamdy6/project.git
   cd project
   ```

2. **(Optional) Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate       # for Linux/Mac
   venv\Scripts\activate          # for Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Flask app**
   ```bash
   python app.py
   ```
   Then open your browser and go to:  
   👉 `http://127.0.0.1:5000`

---

## 📂 Project Structure
```
project/
├── app.py                 # Main Flask app
├── requirements.txt
├── vercel.json            # Vercel deployment config
├── data.xlsx              # Example dataset
├── static/                # CSS, JS, images, etc.
│   └── ...
└── templates/             # HTML templates
    └── ...
```

---

## 🧠 Possible Improvements
- Add user authentication or admin panel
- Support multiple file uploads and comparisons
- Improve chart design and interactivity
- Add database integration (SQLite / PostgreSQL)
- Dark mode or theme toggle

---

## 🤝 Contributing
Contributions are welcome!  
To contribute:
1. Fork the repository  
2. Create a new branch  
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Commit your changes  
   ```bash
   git commit -m "Add new feature"
   ```
4. Push and open a Pull Request  

---

## 📜 License
This project is licensed under the **MIT License**.  
Feel free to use, modify, and distribute as needed.

---

## 🇵🇸 Free Palestine
<div align="center" style="margin-top: 20px;">
  <strong>FREE PALESTINE 🇵🇸</strong>
  <br>
  <em>With justice, peace, and humanity for all.</em>
</div>
