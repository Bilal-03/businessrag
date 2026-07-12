#!/bin/bash
source venv/bin/activate
uvicorn src.api.main:app --reload
