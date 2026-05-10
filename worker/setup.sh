pip install -r requirements.txt
pip install --upgrade transformers
python -m uvicorn worker:app --host 0.0.0.0 --port 8000