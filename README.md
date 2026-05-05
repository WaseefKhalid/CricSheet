# 🏏 PSL Cricket Analytics Portal

A Streamlit-based cricket analytics dashboard for Pakistan Super League (PSL) data.
Upload your ball-by-ball CSV data and explore stats like ESPNcricinfo.

---

## 🚀 Features

- 📂 **Upload ZIP** — drop your entire PSL CSV folder as a ZIP
- 🔍 **Chained Filters** — Season → Team → Venue → Toss → Winner (each filter narrows the next)
- 🏏 **Batting Stats** — Runs, Average, Strike Rate, 100s, 50s, Highest Score
- 🎳 **Bowling Stats** — Wickets, Economy, Average, Bowling SR, Maidens
- 📋 **Match Results** — Full scorecards with Player of the Match
- 🏆 **Team Stats** — Win/Loss records, Toss analysis
- 📈 **Charts** — Runs/Wickets per season, Win methods, Top performers
- ⬇️ **Download** — Export any stats table as CSV

---

## 📁 Expected Data Format

Your ZIP should contain pairs of CSV files per match:

```
psl_data.zip
├── 959175.csv          ← ball-by-ball data
├── 959175_info.csv     ← match info/metadata
├── 959177.csv
├── 959177_info.csv
└── ...
```

### Ball-by-ball CSV columns:
`match_id, season, start_date, venue, innings, ball, batting_team, bowling_team, striker, non_striker, bowler, runs_off_bat, extras, wides, noballs, byes, legbyes, penalty, wicket_type, player_dismissed, ...`

### Info CSV format (key-value style):
```
info,team,Islamabad United
info,team,Quetta Gladiators
info,season,2015/16
info,date,2/4/2016
info,winner,Quetta Gladiators
...
```

---

## 🛠️ Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/psl-cricket-analytics.git
cd psl-cricket-analytics

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

---

## ☁️ Deploy on Streamlit Cloud (Free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set **Main file path** to `app.py`
5. Click **Deploy** — done!

---

## 📊 Stats Calculated

| Category | Metrics |
|----------|---------|
| Batting | Innings, Runs, Highest Score, Average, Strike Rate, 100s, 50s |
| Bowling | Overs, Maidens, Runs, Wickets, Economy, Average, Bowling SR |
| Match | Date, Teams, Toss, Winner, Player of Match |
| Team | Played, Won, Lost, No Result, Win % |
| Toss | Toss wins, Match wins after toss, Win % |

---

## 🗂️ Project Structure

```
psl-cricket-analytics/
├── app.py                    # Main Streamlit app
├── requirements.txt
├── .streamlit/
│   └── config.toml           # Dark theme config
├── utils/
│   ├── data_loader.py        # ZIP/CSV parsing
│   ├── filters.py            # Chained filter logic
│   └── stats.py              # All stats computations
└── components/
    └── charts.py             # Plotly chart functions
```

---

## 🤝 Contributing

Pull requests welcome! Open an issue first to discuss major changes.

---

## 📄 License

MIT
