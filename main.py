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

from schema import PostCreate, PostResponse, PostUpdate, UserCreate, UserResponse, UserUpdate

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload 

import models
from database import Base, engine, get_db

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

@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: DbSession): # Here, we use dependency injection to get a database session for the request.
    result = await db.execute(
        select(models.User).where(models.User.username == user.username)
    )
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user.username}' is already taken."
        )

    result = await db.execute(
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
    await db.commit() # save your database
    await db.refresh(new_user) # reterive the latest data from db
    return new_user

@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: DbSession):
    result = await db.execute(
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

@app.patch("/api/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_update: UserUpdate, db: DbSession):
    result = await db.execute(
            select(models.User).where(models.User.id == user_id)
        )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )

    if user_update.username is not None and user_update.username != user.username:
        result = await db.execute(
            select(models.User).where(models.User.username == user_update.username)
        )
        existing_user = result.scalars().first()

        if existing_user:
            raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Username already exists"
                    )

    if user_update.email is not None and user_update.email != user.email:
        existing_email = await db.execute(
            select(models.User).where(models.User.email == user_update.email)
        ).scalars().first()

        if existing_email:
            raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Email already registered"
                    )

    # this approach is similar as model_dump(exclusive_unset=True)
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.image_file is not None:
        user.image_file = user_update.image_file

    await db.commit()
    await db.refresh(user)
    return user


@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: DbSession):
    result = await db.execute(
            select(models.User).where(models.User.id == user_id)
        )
    user = result.scalars().first()

    
    if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )

    await db.delete(user)
    await db.commit()



@app.get("/api/users/{user_id}/posts", response_model=list[PostResponse])
async def get_user_posts(user_id: int, db: DbSession):
    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )

    # if there is user, show all posts of that user
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == user_id)
    )
    
    posts = result.scalars().all()

    return posts


@app.post("/api/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(post: PostCreate, db: DbSession):
    result = await db.execute(
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
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"]) # Explicitly refresh the specified relationship
    return new_post


@app.get("/api/posts", response_model=list[PostResponse])
async def get_posts(db: DbSession):

    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)))
    posts = result.scalars().all()
    return posts


@app.get("/api/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: DbSession):

    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id)
    )
    post = result.scalars().first()

    if post:
        return post
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id {post_id} not found"
        )

@app.put("/api/posts/{post_id}", response_model=PostResponse)
async def update_post_full(post_id: int, post_data: PostCreate, db: DbSession):

    # Get the post from the database first
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id)
    )
    
    post = result.scalars().first()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id {post_id} not found"
        )

    if post_data.user_id != post.user_id:

        # this check is temporary, because we don't have authentication yet. In the future, we will check if the user is the author of the post, and if not, we will raise an exception.
        result = await db.execute(
            select(models.User).where(models.User.id == post_data.user_id)
        )
        
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {post_data.user_id} not found"
            )

    post.title = post_data.title
    post.content = post_data.content
    post.user_id = post_data.user_id

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post

@app.patch("/api/posts/{post_id}", response_model=PostResponse)
async def update_post_partial(post_id: int, post_data: PostUpdate, db: DbSession):

    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id)
    )
    
    post = result.scalars().first()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id {post_id} not found"
        )

    update_data = post_data.model_dump(exclude_unset=True) # It excludes fields that the client didn't provide.
    for field, value in update_data.items():
        setattr(post, field, value) # It dynamically assigns a value to an object's attribute.

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post

@app.delete("/api/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: int, db: DbSession):

    result = await db.execute(
        select(models.Post)
        .where(models.Post.id == post_id)
    )
    
    post = result.scalars().first()

    await db.delete(post)
    await db.commit()


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