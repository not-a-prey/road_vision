import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Frontend Server")

# Serve the static files (index.html, style.css, app.js) from the current directory
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    # Host on 0.0.0.0 so Docker can map it correctly
    uvicorn.run(app, host="0.0.0.0", port=3000)