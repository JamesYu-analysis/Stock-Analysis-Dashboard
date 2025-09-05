# 📊 Stock Analysis Dashboard

## 🔎 Project Description
This project is an **automated stock analysis dashboard** developed in Python with Streamlit.  
It simplifies complex financial data into **clear visual insights and investment signals**, helping investors quickly evaluate stocks and make informed decisions.

---

## 🎯 Motivation
- 📉 **Complexity**: Financial statements are massive and full of technical jargon.  
- ⏳ **Time-consuming**: Comparing multiple companies requires heavy effort.  
- ⚡ **Inefficiency**: Traditional methods lack a standardized evaluation process.  
- 🚧 **Accessibility**: Non-finance users face high barriers when interpreting data.  

➡️ **We need a tool that transforms complex data into simple, intuitive, and actionable investment insights.**

---

## 🎯 Purpose
The dashboard provides:  
- 🔹 **Data Automation**: Fetch stock & financial data directly from public APIs (`yfinance`).  
- 🔹 **Indicator Calculation**: Compute five key metrics:
  - Earnings Per Share (**EPS**)  
  - Return on Equity (**ROE**)  
  - Price-to-Earnings Ratio (**P/E**)  
  - Price-to-Book Ratio (**P/B**)  
  - Profit Margin  
- 🔹 **Decision Support**: Generate clear investment suggestions (e.g., *Strong Buy, Buy, Hold, Sell, Strong Sell*).  
- 🔹 **Visualization**: Display results with interactive charts and radar plots.  
- 🔹 **Report Export**: One-click generation of **PDF reports**.

---

## 🏗 Framework
1. **Data Extraction (ETL)** → Pull stock data and financial statements.  
2. **Indicator Calculation** → EPS, ROE, P/E, P/B, Profit Margin.  
3. **Scoring Model** → Assign grades (A–F) based on investment benchmarks.  
4. **Visualization** → Interactive charts with Streamlit + Plotly.  
5. **Report Generation** → Export analysis to PDF with ReportLab.  

---

## 🖼 Features
- 📈 **Stock Trend Chart** (switch between Price / Cumulative Return).  
- 📊 **Financial Radar Chart** (multi-stock comparison).  
- 📑 **One-Click PDF Export** with analysis results.  

---

## 🛠 Tech Stack
- **Python**  
- **Streamlit** – Web framework  
- **Plotly** – Visualization  
- **yfinance** – Financial data API  
- **ReportLab** – PDF report generation  

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/JamesYu-analysis/your-repo-name.git
cd your-repo-name
```
### 2. Install dependencies
```bash
pip install -r requirements.txt
```
### 3. Run the app
```bash
streamlit run streamlit_app.py
```
4. Deploy on Streamlit Cloud (optional)
	•	Push your code to GitHub.
	•	Connect your repository to Streamlit Cloud.
	•	Deploy and share your app with a public URL.
