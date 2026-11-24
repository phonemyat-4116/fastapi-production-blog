from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schema import PostResponse, PostCreate, PostUpdate

from auth import CurrentUser

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]

@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(post: PostCreate, current_user: CurrentUser, db: DbSession):

    new_post = models.Post(
        title = post.title,
        content = post.content,
        user_id = current_user.id
    )

    db.add(new_post)
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"]) # Explicitly refresh the specified relationship
    return new_post


@router.get("", response_model=list[PostResponse])
async def get_posts(db: DbSession):

    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)))
    posts = result.scalars().all()
    return posts


@router.get("/{post_id}", response_model=PostResponse)
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

@router.put("/{post_id}", response_model=PostResponse)
async def update_post_full(post_id: int, post_data: PostCreate, current_user: CurrentUser, db: DbSession):


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

    # if post_data.user_id != post.user_id:

        # this check is temporary, because we don't have authentication yet. In the future, we will check if the user is the author of the post, and if not, we will raise an exception.
        #
        # ===== Don't necessary anymore ======
        # result = await db.execute(
        #     select(models.User).where(models.User.id == post_data.user_id)
        # )
        
        # user = result.scalars().first()

        # if not user:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail=f"User with id {post_data.user_id} not found"
        #     )

    # ownership check
    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorize to update this post"
        )

    post.title = post_data.title
    post.content = post_data.content 

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post

@router.patch("/{post_id}", response_model=PostResponse)
async def update_post_partial(post_id: int, post_data: PostUpdate, current_user: CurrentUser, db: DbSession):

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

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorize to update this post"
        )

    update_data = post_data.model_dump(exclude_unset=True) # It excludes fields that the client didn't provide.
    for field, value in update_data.items():
        setattr(post, field, value) # It dynamically assigns a value to an object's attribute.

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: int, current_user: CurrentUser, db: DbSession):

    result = await db.execute(
        select(models.Post)
        .where(models.Post.id == post_id)
    )
    
    post = result.scalars().first()

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorize to update this post"
        )

    await db.delete(post)
    await db.commit()
