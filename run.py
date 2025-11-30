from app import create_app

# Create the Flask app instance for gunicorn
app = create_app()

# For local development
def main() -> None:
    import os
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(debug=True, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()


# Production configuration for gunicorn
if __name__ != "__main__":
    # This runs when imported by gunicorn
    pass


