import logging
from datetime import datetime

import docx
from cerberus import Validator
from docx import Document
from flask_login import current_user
from flask_restful import current_app, Api
from flask import Blueprint, request, send_file, url_for

from app.celery.tasks import create_user_email, export_users_excel, export_users_pdf
from .base import BaseResource
from ..models.user import User as UserModel
from ..libs.libreoffice import convert_to
from ..utils.cerberus_schema import user_model_schema, search_model_schema, MyValidator
from ..utils.decorators import token_required

blueprint = Blueprint('users', __name__, url_prefix='/users')
api = Api(blueprint)

logger = logging.getLogger(__name__)


class UserResource(BaseResource):
    db_model = UserModel


@api.resource('')
class NewUserResource(UserResource):
    @token_required
    def post(self) -> tuple:
        data = request.get_json()

        v = MyValidator(schema=user_model_schema())
        v.allow_unknown = False

        if not v.validate(data):
            return {
                       'message': 'validation error',
                       'fields': v.errors,
                   }, 422

        user = UserModel.create(**data)
        user.created_by = current_user.id
        user_dict = user.serialize()

        create_user_email.delay(data)

        return {
                   'data': user_dict,
               }, 201


@api.resource('/<int:user_id>')
class UserResource(UserResource):
    @token_required
    def get(self, user_id: int) -> tuple:
        response = {
            'error': 'User doesn\'t exist',
        }
        status_code = 404

        user = UserModel.get_or_none(UserModel.id == user_id)

        if isinstance(user, UserModel):
            user_dict = user.serialize()

            response = {
                'data': user_dict,
            }
            status_code = 200

        return response, status_code

    @token_required
    def put(self, user_id: int) -> tuple:
        data = request.get_json()

        v = MyValidator(schema=user_model_schema(False))
        v.allow_unknown = False

        if not v.validate(data):
            return {
                       'message': 'validation error',
                       'fields': v.errors
                   }, 422

        user = (UserModel.get_or_none(UserModel.id == user_id,
                                      UserModel.deleted_at.is_null()))
        if user:
            data['id'] = user_id
            UserModel(**data).save()

            user = (UserModel.get_or_none(UserModel.id == user_id,
                                          UserModel.deleted_at.is_null()))
            user_dict = user.serialize()

            response_data = {
                'data': user_dict,
            }
            response_code = 200
        else:
            response_data = {
                'error': 'User doesn\'t exist',
            }
            response_code = 400

        return response_data, response_code

    @token_required
    def delete(self, user_id: int) -> tuple:
        response = {
            'error': 'User doesn\'t exist',
        }
        status_code = 404

        user = UserModel.get_or_none(UserModel.id == user_id)

        if isinstance(user, UserModel):
            if user.deleted_at is None:
                user.deleted_at = datetime.utcnow()
                user.save()

                user_dict = user.serialize()

                response = {
                    'data': user_dict,
                }
                status_code = 200
            else:
                response = {
                    'error': 'User already deleted',
                }
                status_code = 400

        return response, status_code


@api.resource('/search')
class UsersSearchResource(UserResource):
    @token_required
    def post(self) -> tuple:
        data = request.get_json()

        user_fields = UserModel.get_fields(exclude=['id', 'password'])
        v = Validator(schema=search_model_schema(user_fields))
        v.allow_unknown = False

        if not v.validate(data):
            return {
                       'message': 'validation error',
                       'fields': v.errors,
                   }, 422

        page_number, items_per_page, order_by = self.get_request_query_fields(data)

        query = UserModel.select()
        records_total = query.count()

        query = self.create_query(query, data)

        query = (query.order_by(order_by)
                 .paginate(page_number, items_per_page))

        records_filtered = query.count()
        user_list = []

        for user in query:
            user_dict = user.serialize()
            user_list.append(user_dict)

        return {
                   'data': user_list,
                   'records_total': records_total,
                   'records_filtered': records_filtered,
               }, 200


@api.resource('/xlsx')
class ExportUsersExcelResource(UserResource):
    @token_required
    def post(self) -> tuple:
        data = request.get_json()

        page_number, items_per_page, order_by = self.get_request_query_fields()

        query = UserModel.select()
        query = self.create_query(query, data)
        query = (query.order_by(order_by)
                 .paginate(page_number, items_per_page))

        user_list = []
        for user in query:
            user_list.append(user.serialize())

        task = export_users_excel.delay(created_by=current_user.id, user_list=user_list)

        return {
                   'task': task.id,
                   'url': url_for('tasks.taskstatusresource', task_id=task.id, _external=True),
               }, 202


@api.resource('/pdf')
class ExportUsersPdfResource(UserResource):
    @token_required
    def post(self) -> tuple:
        data = request.get_json()

        page_number, items_per_page, order_by = self.get_request_query_fields()

        query = UserModel.select()
        query = self.create_query(query, data)
        query = (query.order_by(order_by)
                 .paginate(page_number, items_per_page))

        user_list = []
        for user in query:
            user_list.append(user.serialize())

        task = export_users_pdf.apply_async(args=[current_user.id, user_list])

        return {
            'task': task.id,
            'url': url_for('tasks.taskstatusresource', task_id=task.id, _external=True),
        }, 202
