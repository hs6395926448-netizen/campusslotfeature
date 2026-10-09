from dataset_loader import load_dataset
from app import create_app
app=create_app("development")
with app.app_context(): print(load_dataset(reset=True))
