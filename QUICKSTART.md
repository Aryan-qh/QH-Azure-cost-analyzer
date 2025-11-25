# 1. Setup backend
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2. Configure .env with Azure credentials

# 3. Start backend
python -m app.main

# 4. Start frontend (new terminal)
cd frontend
python -m http.server 3000

# 5. Open http://localhost:3000