
from pathlib import Path
import json

# =====================================================
# 1. PROJECT ROOT PATH
# =====================================================

PROJECT_ROOT = Path(
    r"C:\Users\LENOVO\Desktop\WasteWise AI — Smart Waste Management System"
)

# =====================================================
# 2. COMPLETE PROJECT STRUCTURE
# =====================================================

PROJECT_STRUCTURE = {
    "frontend": {
        "public": {},
        "src": {
            "assets": {},
            "components": {
                "common": {},
                "charts": {},
                "tables": {},
                "forms": {},
            },
            "layouts": {
                "MainLayout.tsx": None,
                "AuthLayout.tsx": None,
            },
            "pages": {
                "Login.tsx": None,
                "Dashboard.tsx": None,
                "Products.tsx": None,
                "Inventory.tsx": None,
                "SalesHistory.tsx": None,
                "DemandForecast.tsx": None,
                "ExpiryRisk.tsx": None,
                "Recommendations.tsx": None,
                "WasteReports.tsx": None,
                "ModelMetrics.tsx": None,
            },
            "services": {
                "api.ts": None,
                "products.ts": None,
                "inventory.ts": None,
                "predictions.ts": None,
            },
            "hooks": {},
            "types": {},
            "utils": {},
            "App.tsx": None,
            "main.tsx": None,
        },
        "package.json": None,
        "vite.config.ts": None,
    },

    "backend": {
        "app": {
            "api": {
                "v1": {
                    "auth.py": None,
                    "dashboard.py": None,
                    "products.py": None,
                    "batches.py": None,
                    "sales.py": None,
                    "forecasts.py": None,
                    "risk.py": None,
                    "recommendations.py": None,
                    "waste.py": None,
                }
            },
            "core": {
                "config.py": None,
                "security.py": None,
            },
            "db": {
                "session.py": None,
                "base.py": None,
            },
            "models": {
                "user.py": None,
                "product.py": None,
                "inventory.py": None,
                "sales.py": None,
                "prediction.py": None,
            },
            "schemas": {},
            "services": {
                "inventory_service.py": None,
                "forecast_service.py": None,
                "recommendation_service.py": None,
            },
            "repositories": {},
            "main.py": None,
            "dependencies.py": None,
        },
        "tests": {},
        "requirements.txt": None,
        ".env.example": None,
    },

    "ml": {
        "data": {
            "raw": {},
            "interim": {},
            "processed": {},
        },
        "notebooks": {
            "01_data_understanding.ipynb": None,
            "02_eda.ipynb": None,
            "03_feature_engineering.ipynb": None,
            "04_demand_forecasting.ipynb": None,
            "05_expiry_risk_model.ipynb": None,
            "06_model_evaluation.ipynb": None,
        },
        "src": {
            "data_validation.py": None,
            "preprocessing.py": None,
            "feature_engineering.py": None,
            "train_forecast.py": None,
            "train_expiry_risk.py": None,
            "evaluate.py": None,
            "predict.py": None,
        },
        "artifacts": {},
        "tests": {},
        "requirements.txt": None,
    },

    "database": {
        "schema.sql": None,
        "seed_data.sql": None,
        "migrations": {},
    },

    "scripts": {
        "import_dataset.py": None,
        "generate_demo_data.py": None,
        "validate_data.py": None,
    },

    "docs": {
        "project_report.md": None,
        "api_documentation.md": None,
        "database_design.md": None,
        "model_card.md": None,
    },

    "docker-compose.yml": None,
    ".gitignore": None,
    "README.md": None,
}


# =====================================================
# 3. CREATE A VALID JUPYTER NOTEBOOK
# =====================================================

def create_notebook(path: Path) -> None:
    """Write a valid Jupyter Notebook JSON document."""

    title = path.stem.replace("_", " ").title()

    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"# {title}\n",
                    "\n",
                    "## WasteWise AI — Smart Waste Management System\n",
                    "\n",
                    "Project analysis and machine learning experiments."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "from pathlib import Path\n",
                    "import pandas as pd\n",
                    "import numpy as np\n",
                    "import matplotlib.pyplot as plt\n",
                    "\n",
                    'print("WasteWise AI notebook is ready!")'
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }

    path.write_text(
        json.dumps(notebook, indent=2),
        encoding="utf-8"
    )


# =====================================================
# 4. CREATE FOLDERS AND FILES RECURSIVELY
# =====================================================

def create_structure(base_path: Path, structure: dict) -> None:
    """Create all directories and files in the structure."""

    for name, content in structure.items():
        path = base_path / name

        if isinstance(content, dict):
            path.mkdir(parents=True, exist_ok=True)
            create_structure(path, content)

        elif content is None:
            path.parent.mkdir(parents=True, exist_ok=True)

            # Create valid notebook files
            if path.suffix == ".ipynb":
                if not path.exists() or path.stat().st_size == 0:
                    create_notebook(path)
                    print(f"[NOTEBOOK] {path}")
                else:
                    print(f"[SKIP] Existing notebook preserved: {path}")

            # Create ordinary empty files
            elif not path.exists():
                path.touch()
                print(f"[FILE] {path}")

            else:
                print(f"[SKIP] Existing file preserved: {path}")


# =====================================================
# 5. CREATE README CONTENT
# =====================================================

def create_readme() -> None:
    readme_path = PROJECT_ROOT / "README.md"

    if not readme_path.exists() or readme_path.stat().st_size == 0:
        content = """# WasteWise AI
## Smart Inventory and Waste Management System

### Main features
- Product and inventory management
- Sales history
- Demand forecasting
- Product expiry-risk analysis
- Inventory recommendations
- Waste reporting
- Machine learning model evaluation
- React + TypeScript frontend
- Python backend API
- SQL database

### Project folders
- `frontend/`: User interface
- `backend/`: API and business logic
- `ml/`: Machine learning workflows
- `database/`: SQL scripts
- `scripts/`: Data utilities
- `docs/`: Project documentation

### Important
The generated source files are starter placeholders.
Application logic, database integration, and ML models
must be implemented before the full application can run.
"""
        readme_path.write_text(content, encoding="utf-8")
        print(f"[README] {readme_path}")


# =====================================================
# 6. MAIN FUNCTION
# =====================================================

def main():
    print("=" * 65)
    print("WASTEWISE AI PROJECT SETUP")
    print("=" * 65)

    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"\nProject root:\n{PROJECT_ROOT}\n")

    create_structure(PROJECT_ROOT, PROJECT_STRUCTURE)
    create_readme()

    # Confirm all requested notebook files exist
    notebook_dir = PROJECT_ROOT / "ml" / "notebooks"

    print("\nJUPYTER NOTEBOOKS")
    print("-" * 65)

    for notebook in sorted(notebook_dir.glob("*.ipynb")):
        print(f"{notebook.name} | {notebook.stat().st_size} bytes")

    print("\n" + "=" * 65)
    print("PROJECT STRUCTURE CREATED SUCCESSFULLY!")
    print(f"Location: {PROJECT_ROOT}")
    print("=" * 65)


if __name__ == "__main__":
    main()
