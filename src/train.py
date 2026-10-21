from pathlib import Path
import json
import tensorflow as tf
import matplotlib.pyplot as plt
from tensorflow.keras import layers, models

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"
MODEL_DIR = ROOT / "models"
ARTIFACT_DIR = ROOT / "artifacts"

IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
EPOCHS = 8
SEED = 42

def main():
    MODEL_DIR.mkdir(exist_ok=True)
    ARTIFACT_DIR.mkdir(exist_ok=True)

    if not DATA_DIR.exists():
        raise SystemExit(f"Dataset folder missing: {DATA_DIR}")

    class_dirs = [
        p for p in DATA_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ]

    if len(class_dirs) < 2:
        raise SystemExit(
            "Add at least two class folders with images inside data/raw/. "
            "Example: data/raw/plastic/ and data/raw/paper/"
        )

    train_ds = tf.keras.utils.image_dataset_from_directory(
        DATA_DIR,
        validation_split=0.2,
        subset="training",
        seed=SEED,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE
    )

    val_ds = tf.keras.utils.image_dataset_from_directory(
        DATA_DIR,
        validation_split=0.2,
        subset="validation",
        seed=SEED,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE
    )

    class_names = train_ds.class_names
    print("Classes:", class_names)

    autotune = tf.data.AUTOTUNE
    train_ds = train_ds.prefetch(autotune)
    val_ds = val_ds.prefetch(autotune)

    # Transfer learning using pretrained MobileNetV2
    base_model = tf.keras.applications.MobileNetV2(
        input_shape=(224, 224, 3),
        include_top=False,
        weights="imagenet"
    )
    base_model.trainable = False

    inputs = layers.Input(shape=(224, 224, 3))
    x = layers.Rescaling(1.0 / 127.5, offset=-1)(inputs)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(
        len(class_names), activation="softmax"
    )(x)

    model = models.Model(inputs, outputs)

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=3,
            restore_best_weights=True
        )
    ]

    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=EPOCHS,
        callbacks=callbacks
    )

    val_loss, val_accuracy = model.evaluate(val_ds, verbose=0)

    model.save(MODEL_DIR / "wastewise_model.keras")

    (MODEL_DIR / "class_names.json").write_text(
        json.dumps(class_names, indent=2),
        encoding="utf-8"
    )

    metrics = {
        "validation_loss": float(val_loss),
        "validation_accuracy": float(val_accuracy),
        "classes": class_names,
        "epochs_completed": len(history.history["loss"])
    }

    (ARTIFACT_DIR / "metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8"
    )

    plt.figure(figsize=(8, 5))
    plt.plot(history.history["accuracy"], label="Training accuracy")
    plt.plot(history.history["val_accuracy"], label="Validation accuracy")
    plt.xlabel("Epoch")
    plt.ylabel("Accuracy")
    plt.title("WasteWise AI Training History")
    plt.legend()
    plt.tight_layout()
    plt.savefig(ARTIFACT_DIR / "training_history.png")
    plt.close()

    print("\\nTraining complete!")
    print("Validation accuracy:", round(val_accuracy * 100, 2), "%")
    print("Model:", MODEL_DIR / "wastewise_model.keras")
    print("Note: validation results are not independent test results.")

if __name__ == "__main__":
    main()
