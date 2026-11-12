from typing import Annotated

from http import HTTPStatus
from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
# from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from schema import PostCreate, PostResponse, UserCreate, UserResponse

from sqlalchemy import select
from sqlalchemy.orm import Session

import models
from database import Base, engine, get_db

Base.metadata.create_all(bind=engine) # Create the database tables based on the models defined in models.py

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

templates = Jinja2Templates(directory="templates")

DbSession = Annotated[Session, Depends(get_db)] # This is a dependency that provides a database session to your route handlers. It ensures that the session is properly closed after use.


# posts: list[dict] = [
#     {
#         "id": 1,
#         "author": "Corey Schafer",
#         "title": "FastAPI is Awesome",
#         "content": "This framework is really easy to use and super fast.",
#         "date_posted": "April 20, 2025",
#     },
#     {
#         "id": 2,
#         "author": "Jane Doe",
#         "title": "Python is Great for Web Development",
#         "content": "Python is a great language for web development, and FastAPI makes it even better",
#         "date_posted": "April 21, 2025",
#     }
# ]


# @app.get("/", response_class=HTMLResponse, include_in_schema=False) # include_in_schema=False means that this route will not be included in the doc
# @app.get("/posts", response_class=HTMLResponse)


# =============== HTML Pages ================

@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
def home(request: Request, db: DbSession):
    posts = db.execute(select(models.Post)).scalars().all()

    return templates.TemplateResponse(
        request=request, 
        name="home.html", 
        context={"posts": posts, "title": "Home"}
    )


@app.get("/posts/{post_id}", include_in_schema=False)
def post_page(request: Request, post_id: int, db: DbSession):

    post = db.execute(
        select(models.Post).where(models.Post.id == post_id)
    ).scalars().first()

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
def user_posts_page(request: Request, user_id: int, db: DbSession):

    user = db.execute(
        select(models.User).where(models.User.id == user_id)
    ).scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )

    posts = db.execute(
        select(models.Post).where(models.Post.user_id == user_id)
    ).scalars().all()

    return templates.TemplateResponse(
        request=request, 
        name="user_posts.html", 
        context={"posts": posts, "user": user, "title": f"{user.username}'s Posts"}
    )

# ================ API Endpoints ================

@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: DbSession): # Here, we use dependency injection to get a database session for the request.
    result = db.execute(
        select(models.User).where(models.User.username == user.username)
    )
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user.username}' is already taken."
        )

    result = db.execute(
        select(models.User).where(models.User.email == user.email)
    )
    existing_email = result.scalars().first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{user.email}' is already registered."
        )

    new_user = models.User(
        username=user.username,
        email=user.email
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: DbSession):
    result = db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    user = result.scalars().first()

    if user:
        return user
    else:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f"User with id {user_id} not found"
        )

@app.get("/api/users/{user_id}/posts", response_model=list[PostResponse])
def get_user_posts(user_id: int, db: DbSession):
    user = db.execute(
        select(models.User).where(models.User.id == user_id)
    ).scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )

    # if there is user, show all posts of that user
    posts = db.execute(
        select(models.Post).where(models.Post.user_id == user_id)
    ).scalars().all()

    return posts


@app.post("/api/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(post: PostCreate, db: DbSession):
    result = db.execute(
        select(models.User).where(models.User.id == post.user_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found"
        )

    new_post = models.Post(
        title = post.title,
        content = post.content,
        user_id = post.user_id
    )

    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@app.get("/api/posts", response_model=list[PostResponse])
def get_posts(db: DbSession):

    result = db.execute(select(models.Post))
    posts = result.scalars().all()
    return posts


@app.get("/api/posts/{post_id}", response_model=PostResponse)
def get_post(post_id: int, db: DbSession):

    result = db.execute(
        select(models.Post).where(models.Post.id == post_id)
    )
    post = result.scalars().first()

    if post:
        return post
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id {post_id} not found"
        )



# ================ Exception Handling ================

@app.exception_handler(StarletteHTTPException) # This is a custom exception handler for HTTP exceptions. It will catch any HTTPException raised in the application and return a JSON response with the error details.
def general_http_exception_handler(request: Request, exception: StarletteHTTPException):

    message = (
        exception.detail
        if exception.detail
        else "An error occurred while processing your request."
    )

    # for API client requests
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail": message},
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
def validation_exception_handler(request: Request, exception: RequestValidationError):

    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exception.errors()},
        )

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
# 5. We use Pydantic models to validate request data and define response models for our API endpoints. Use schema.py, where we create Pydantic models for PostCreate and PostResponse.



# {
#   "title": "DevOps is IMPORTANT",
#   "content": "Here is Devops contents that everyone wants",
#   "author": "Kevin Jones"
# }