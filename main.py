from typing import Annotated

from contextlib import asynccontextmanager

from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler

from http import HTTPStatus
from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.exceptions import RequestValidationError
# from fastapi.responses import JSONResponse
# from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload 

import models
from database import Base, engine, get_db

from routers import posts, users

# sync
# Base.metadata.create_all(bind=engine) # Create the database tables based on the models defined in models.py

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Start up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shut down
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

templates = Jinja2Templates(directory="templates")

DbSession = Annotated[AsyncSession, Depends(get_db)] # This is a dependency that provides a database session to your route handlers. It ensures that the session is properly closed after use.

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])

# =============== HTML Pages ================

@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
async def home(request: Request, db: DbSession):
    result = await db.execute(
        select(models.Post).options(selectinload(models.Post.author)) # this .options...... is eager loading
    )

    posts = result.scalars().all()

    return templates.TemplateResponse(
        request=request, 
        name="home.html", 
        context={"posts": posts, "title": "Home"}
    )


@app.get("/posts/{post_id}", include_in_schema=False)
async def post_page(request: Request, post_id: int, db: DbSession):

    result = await db.execute(

        select(models.Post)
        .options(selectinload(models.Post.author)) # eager loading
        .where(models.Post.id == post_id)

    )
    
    post = result.scalars().first()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id {post_id} not found"
        )

    return templates.TemplateResponse(
        request=request, 
        name="post.html", 
        context={"post": post, "title": post.title[:50]}
    )

@app.get("/users/{user_id}/posts", include_in_schema=False, name="user_posts")
async def user_posts_page(request: Request, user_id: int, db: DbSession):

    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )

    results = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author)) # eager loading
        .where(models.Post.user_id == user_id)
    )
    
    posts = results.scalars().all()

    return templates.TemplateResponse(
        request=request, 
        name="user_posts.html", 
        context={"posts": posts, "user": user, "title": f"{user.username}'s Posts"}
    )

# ================ API Endpoints ================

# APIs are handled by routers


# ================ Exception Handling ================

@app.exception_handler(StarletteHTTPException) # This is a custom exception handler for HTTP exceptions. It will catch any HTTPException raised in the application and return a JSON response with the error details.
async def general_http_exception_handler(request: Request, exception: StarletteHTTPException):

    # for API client requests
    # if request.url.path.startswith("/api"):
    #     return JSONResponse(
    #         status_code=exception.status_code,
    #         content={"detail": message},
    #     )

    if request.url.path.startswith("/api"):
        return await http_exception_handler(request, exception) # handle by async exception handler

    # now message are also used for template response
    message = (
            exception.detail
            if exception.detail
            else "An error occurred while processing your request."
        )

    # for browser requests
    return templates.TemplateResponse(
        request=request, 
        name="error.html", 
        context={
            "status_code": exception.status_code,
            "title": HTTPStatus(exception.status_code).phrase,
            "message": message,
        },
        status_code=exception.status_code
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exception: RequestValidationError):

    if request.url.path.startswith("/api"):
        # return JSONResponse(
        #     status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        #     content={"detail": exception.errors()},
        # )
        return await request_validation_exception_handler(request, exception)

    return templates.TemplateResponse(
        request=request, 
        name="error.html", 
        context={
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "title": HTTPStatus(status.HTTP_422_UNPROCESSABLE_ENTITY).phrase,
            "message": "Invalid request data. Please check your input and try again.",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )








# List of what I've learned so far:

# 1. Jinja2 Template usage
# 2. url_for() function to generate URLs for route and static files
# 3. Path parameters in FastAPI routes
# 4. Custom exception handling and validation for both API and browser requests
# 5. Use Pydantic models to validate request data and define response models for our API endpoints. Use schema.py, where we create Pydantic models for PostCreate and PostResponse.
# 6. Use SQLArchemy to define the actual database models and relationship
# 7. Change the sync way to async



# {
#   "title": "DevOps is IMPORTANT",
#   "content": "Here is Devops contents that everyone wants",
#   "author": "Kevin Jones"
# }