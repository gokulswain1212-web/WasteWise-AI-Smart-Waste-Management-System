from pathlib import Path
import json
import sys
import numpy as np
import tensorflow as tf
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "wastewise_model.keras"
CLASS_PATH = ROOT / "models" / "class_names.json"

def predict_image(image_path):
    if not MODEL_PATH.exists() or not CLASS_PATH.exists():
        raise FileNotFoundError(
            "Train the model first: python src/train.py"
        )

    with CLASS_PATH.open("r", encoding="utf-8") as f:
        classes = json.load(f)

    model = tf.keras.models.load_model(MODEL_PATH)
    image = Image.open(image_path).convert("RGB").resize((224, 224))
    array = np.asarray(image, dtype=np.float32)[None, ...]

    scores = model.predict(array, verbose=0)[0]
    index = int(np.argmax(scores))
    return classes[index], float(scores[index])

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            'Usage: python src/predict.py "C:\\path\\to\\image.jpg"'
        )

    label, score = predict_image(sys.argv[1])
    print("Predicted category:", label)
    print(f"Confidence: {score:.2%}")
