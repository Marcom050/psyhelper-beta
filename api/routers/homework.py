"""Homework routes backed by the existing homework service."""

from dataclasses import asdict

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import account_bundle, current_username, parse_body
from api.exceptions import APIValidationError, AuthenticationError
from api.schemas.homework import (
    HomeworkAssignmentRequest,
    HomeworkAssignmentResponse,
    HomeworkResponse,
    HomeworkSubmissionRequest,
    HomeworkSubmissionResponse,
)
from services import auth_service, homework_service


def _assert_can_access(request: Request, username: str) -> str:
    requested = auth_service.normalize_username(username)
    authenticated = current_username(request)
    if requested != authenticated:
        raise AuthenticationError("X-Username must match requested client")
    return requested


def _homework_response(username: str, wellness: dict) -> HomeworkResponse:
    assignments = homework_service.get_assigned_homework(wellness)
    submissions = homework_service.get_submitted_homework(wellness)
    statuses = [asdict(status) for status in homework_service.homework_statuses(assignments, submissions)]
    return HomeworkResponse(username=username, assignments=assignments, submissions=submissions, statuses=statuses)

router = APIRouter()


async def get_homework(request: Request):
    username = _assert_can_access(request, request.path_params["username"])
    response = _homework_response(username, account_bundle(username)["wellness"])
    return JSONResponse(response.model_dump())


async def create_homework_assignment(request: Request):
    username = _assert_can_access(request, request.path_params["username"])
    body = await parse_body(request, HomeworkAssignmentRequest)
    try:
        assignment = homework_service.create_assignment(
            body.template,
            body.due_date,
            body.assigned_by or current_username(request),
            prompt=body.prompt,
        )
    except (KeyError, ValueError) as exc:
        raise APIValidationError("Invalid homework assignment") from exc

    bundle = account_bundle(username)
    wellness = bundle["wellness"]
    wellness.setdefault("homework_assignments", []).append(assignment)
    auth_service.save_account_bundle(username, bundle["profile"], bundle["messages"], wellness)
    response = HomeworkAssignmentResponse(username=username, assignment=assignment, wellness=wellness)
    return JSONResponse(response.model_dump())


async def create_homework_submission(request: Request):
    body = await parse_body(request, HomeworkSubmissionRequest)
    username = _assert_can_access(request, body.username)
    try:
        submission = homework_service.create_submission(body.assignment_id, body.template, body.prompt, body.answer)
    except ValueError as exc:
        raise APIValidationError("Invalid homework submission") from exc

    bundle = account_bundle(username)
    wellness = bundle["wellness"]
    wellness.setdefault("homework_submissions", []).append(submission)
    auth_service.save_account_bundle(username, bundle["profile"], bundle["messages"], wellness)
    response = HomeworkSubmissionResponse(username=username, submission=submission, wellness=wellness)
    return JSONResponse(response.model_dump())

router.add_api_route("/clients/{username}/homework", get_homework, methods=["GET"])
router.add_api_route("/clients/{username}/homework-assignments", create_homework_assignment, methods=["POST"])
router.add_api_route("/homework-submissions", create_homework_submission, methods=["POST"])
