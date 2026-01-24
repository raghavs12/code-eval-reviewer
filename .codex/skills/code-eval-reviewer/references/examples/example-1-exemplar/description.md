## Title

Add response header validation for GET routes

## Problem Brief

FastAPI validates request headers with Header() and response bodies with response_model, but there's no way to validate response headers.

Without this, developers can't catch bugs where headers are missing, have wrong types, or contain invalid values. These issues usually only show up at runtime or in production.

## Agent Instructions

I'd like to add response header validation to match FastAPI's existing validation patterns.

We can do this by adding response_headers parameter to GET route decorators. It should accept a Pydantic model that defines what headers are expected.

The validation happens after the route handler runs. If headers don't match the model, raise an error so developers catch it during testing.

This keeps the same pattern FastAPI uses for other validation and works alongside existing features.

## Technical Requirements

