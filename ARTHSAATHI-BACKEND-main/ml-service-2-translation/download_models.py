import os
import sys
from dotenv import load_dotenv
load_dotenv()
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit import IndicProcessor

MODELS = [
    "prajdabre/rotary-indictrans2-en-indic-dist-200M",
    "prajdabre/rotary-indictrans2-indic-en-dist-200M",
]

def download_all():
    print("Starting pre-download of IndicTrans2 models...")
    token = os.getenv("HF_TOKEN")
    for model_name in MODELS:
        print(f"\nDownloading: {model_name}")
        try:
            print("Downloading tokenizer...")
            AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, token=token)
            print("Downloading model weights...")
            AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True, token=token)
            print(f"Successfully downloaded: {model_name}")
        except Exception as e:
            print(f"Warning: Could not pre-download {model_name}: {e}. It will be downloaded on-demand at runtime.", file=sys.stderr)
            
    print("\nInitializing IndicProcessor to verify resources...")
    try:
        IndicProcessor(inference=True)
        print("IndicProcessor loaded successfully.")
    except Exception as e:
        print(f"Warning: Could not initialize IndicProcessor: {e}. It will be initialized at runtime.", file=sys.stderr)
        
    print("\nPre-download step completed.")

if __name__ == "__main__":
    download_all()
