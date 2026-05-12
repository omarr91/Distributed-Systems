FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install -r requirements.txt
RUN python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; \
    model = AutoModelForCausalLM.from_pretrained('facebook/opt-125m', low_cpu_mem_usage=True); \
    tokenizer = AutoTokenizer.from_pretrained('facebook/opt-125m'); \
    model.save_pretrained('./model_cache'); \
    tokenizer.save_pretrained('./model_cache')"

COPY . .

CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "8000"]