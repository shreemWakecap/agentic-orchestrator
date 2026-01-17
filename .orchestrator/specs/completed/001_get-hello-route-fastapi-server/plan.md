# Plan: Add GET /hello route to FastAPI server in server/app.py that returns {message: Hello World}

Request: Add GET /hello route to FastAPI server in server/app.py that returns {message: Hello World}
Complexity: simple

## Goal

Add a new GET /hello endpoint at root level that returns {"message": "Hello World"}

## Context

- FastAPI server exists at .orchestrator/server/app.py with established route patterns
- Similar endpoint exists at /api/hello (line 149-152) returning lowercase "hello world"
- New route should be at /hello (root level), not /api/hello, with capitalized "Hello World"

## Steps

1. Add GET /hello route to app.py
   DO: Add a new GET endpoint at path "/hello" in the HTML Routes section that returns a JSON response with {"message": "Hello World"}. Follow the existing pattern from the /api/hello endpoint at line 149, but place this in the HTML Routes section since it's a root-level route.
   IN: .orchestrator/server/app.py
   OUT: .orchestrator/server/app.py
   DONE: Route exists in file with @app.get("/hello") decorator and returns {"message": "Hello World"}
   NEEDS: none
