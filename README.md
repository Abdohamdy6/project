# 🧮 AFM26 Results & Analysis Web App  
![Flask](https://img.shields.io/badge/Flask-2.0+-black?logo=flask)
![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-black?logo=vercel)
![License: MIT](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-success)

_A Flask-based web application for visualizing student performance data and generating reports._

---

## 🧭 Overview  
The **AFM26 Results & Analysis Web App** provides a simple and interactive interface for exploring student result data.  
Users can upload Excel files (e.g., `data.xlsx`, `24.xlsx`, `25.xlsx`), view detailed tables and charts, and export the full dashboard — including a **“Free Palestine”** banner — as a **PDF report**.

---

## ⚙️ Features  
✅ Upload and display Excel result files  
✅ View ranked student results in interactive tables  
✅ Generate visual performance charts  
✅ Export entire view (tables + charts + banner) as PDF  
✅ “Free Palestine” footer banner integrated  
✅ Fully deployed and accessible via **Vercel**

---

## 🛠️ Tech Stack  
| Layer | Technologies |
|-------|---------------|
| **Frontend** | HTML, CSS, JavaScript, Chart.js, jsPDF, html2canvas |
| **Backend** | Flask (Python) |
| **Data Handling** | Pandas |
| **Deployment** | Vercel |
| **Version Control** | Git + GitHub |

---

## 🚀 Getting Started (Local Setup)

### 1. Clone the repository  
```bash
git clone https://github.com/Abdohamdy6/project.git
cd project
```

### 2. Create & activate a virtual environment (recommended)  
```bash
python -m venv venv
source venv/bin/activate        # On Linux/macOS
venv\Scripts\activate           # On Windows
```

### 3. Install dependencies  
```bash
pip install -r requirements.txt
```

### 4. Run the Flask app  
```bash
python app.py
```
Then open: [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 📁 Project Structure  
```
project/
├── app.py                 # Main Flask application
├── requirements.txt       # Dependencies list
├── vercel.json            # Vercel deployment config
├── data.xlsx              # Example dataset
├── 24.xlsx / 25.xlsx      # Additional datasets
├── static/                # Static files (CSS, JS, images)
│   ├── style.css
│   └── ...
└── templates/             # HTML templates
    ├── index.html
    └── ...
```

---

## 🧩 Future Improvements  
🔹 Add login/authentication (student & admin views)  
🔹 Support multiple Excel uploads + comparisons  
🔹 Add interactive filters and sorting in tables  
🔹 Integrate database (SQLite/PostgreSQL)  
🔹 Add dark/light mode toggle  
🔹 Improve UI with modern dashboard styling  

---

## 🤝 Contributing  
Contributions are welcome!  
1. Fork the repository  
2. Create a new branch:  
   ```bash
   git checkout -b feature/your-feature
   ```  
3. Commit changes:  
   ```bash
   git commit -m "Add your feature"
   ```  
4. Push and open a Pull Request 🎉  

---

## 📄 License  
This project is licensed under the **MIT License** — free to use, modify, and distribute.

---

## ✊ Free Palestine  
> **FREE PALESTINE 🇵🇸** — With justice, peace, and humanity for all.

---

## 🌐 Live Demo  
🔗 [View Deployed App on Vercel](https://project-kappa-sooty-15.vercel.app)
