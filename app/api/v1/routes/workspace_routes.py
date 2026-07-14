from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.workspace_schema import (
    AIConfigurationResponse,
    AIConfigurationUpsert,
    BusinessProfileResponse,
    BusinessProfileUpsert,
    KnowledgeDocumentResponse,
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.common.messages import ErrorMessage, SuccessMessage, WorkspaceMessages, ErrorMessages
from app.db.session import get_db
from app.knowledge.tasks import process_knowledge_document
from app.middlewares.auth_middleware import require_auth
from app.services.generation_tasks import run_generation_cycle
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])

##tested
@router.post(
    "",
    response_model=SuccessMessage,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = service.create_workspace(payload, user_id)
        workspace = result["workspace"]
        return SuccessMessage(
            message=WorkspaceMessages.WORKSPACE_CREATED,
            data={"workspace": WorkspaceResponse.model_validate(workspace).model_dump(mode="json")},
            code=status.HTTP_201_CREATED,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )

###tested
@router.get("", response_model=SuccessMessage)
async def list_workspaces(
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = service.list_workspaces(user_id)
        workspaces = [WorkspaceResponse.model_validate(w).model_dump(mode="json") for w in result["workspaces"]]
        return SuccessMessage(
            message=WorkspaceMessages.WORKSPACES_RETRIEVED,
            data={"workspaces": workspaces},
            code=status.HTTP_200_OK,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )

##tested
@router.get("/{workspace_id}", response_model=SuccessMessage)
async def get_workspace(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = service.get_workspace(workspace_id, user_id)
        workspace = result["workspace"]
        return SuccessMessage(
            message=WorkspaceMessages.WORKSPACE_RETRIEVED,
            data={"workspace": WorkspaceResponse.model_validate(workspace).model_dump(mode="json")},
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )

##tested
@router.patch("/{workspace_id}", response_model=SuccessMessage)
async def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = service.update_workspace(workspace_id, payload, user_id)
        workspace = result["workspace"]
        return SuccessMessage(
            message=WorkspaceMessages.WORKSPACE_UPDATED,
            data={"workspace": WorkspaceResponse.model_validate(workspace).model_dump(mode="json")},
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )

##tested
@router.post("/{workspace_id}/business-profile", response_model=SuccessMessage)
async def upsert_business_profile(
    workspace_id: UUID,
    payload: BusinessProfileUpsert,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = service.upsert_business_profile(workspace_id, payload, user_id)
        profile = result["business_profile"]
        return SuccessMessage(
            message=WorkspaceMessages.BUSINESS_PROFILE_UPSERTED,
            data={"business_profile": BusinessProfileResponse.model_validate(profile).model_dump(mode="json")},
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )

##tested
@router.get("/{workspace_id}/business-profile", response_model=SuccessMessage)
async def get_business_profile(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = service.get_business_profile(workspace_id, user_id)
        profile = result["business_profile"]
        return SuccessMessage(
            message=WorkspaceMessages.BUSINESS_PROFILE_RETRIEVED,
            data={"business_profile": BusinessProfileResponse.model_validate(profile).model_dump(mode="json")},
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )

##tested
@router.post("/{workspace_id}/ai-configuration", response_model=SuccessMessage)
async def upsert_ai_configuration(
    workspace_id: UUID,
    payload: AIConfigurationUpsert,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = service.upsert_ai_configuration(workspace_id, payload, user_id)
        ai_config = result["ai_configuration"]
        return SuccessMessage(
            message=WorkspaceMessages.AI_CONFIG_UPSERTED,
            data={"ai_configuration": AIConfigurationResponse.model_validate(ai_config).model_dump(mode="json")},
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )

##tested
@router.get("/{workspace_id}/ai-configuration", response_model=SuccessMessage)
async def get_ai_configuration(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = service.get_ai_configuration(workspace_id, user_id)
        ai_config = result["ai_configuration"]
        return SuccessMessage(
            message=WorkspaceMessages.AI_CONFIG_RETRIEVED,
            data={"ai_configuration": AIConfigurationResponse.model_validate(ai_config).model_dump(mode="json")},
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )

##tested
@router.post("/{workspace_id}/knowledge-base/documents", response_model=SuccessMessage)
async def upload_knowledge_document(
    workspace_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = await service.upload_knowledge_document(workspace_id, file, user_id)
        doc = result["document"]
        background_tasks.add_task(process_knowledge_document, str(doc.id))
        return SuccessMessage(
            message=WorkspaceMessages.DOCUMENT_UPLOADED,
            data={"document": KnowledgeDocumentResponse.model_validate(doc).model_dump(mode="json")},
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )

##TESTED
@router.get("/{workspace_id}/knowledge-base/documents", response_model=SuccessMessage)
async def list_knowledge_documents(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = service.list_knowledge_documents(workspace_id, user_id)
        docs = [KnowledgeDocumentResponse.model_validate(d).model_dump(mode="json") for d in result["documents"]]
        return SuccessMessage(
            message=WorkspaceMessages.DOCUMENTS_RETRIEVED,
            data={"documents": docs},
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.delete("/{workspace_id}/knowledge-base/documents/{document_id}", response_model=SuccessMessage)
async def delete_knowledge_document(
    workspace_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        service.delete_knowledge_document(workspace_id, document_id, user_id)
        return SuccessMessage(
            message=WorkspaceMessages.DOCUMENT_DELETED,
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )

@router.post("/{workspace_id}/generate-now")
async def generate_now(
    workspace_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = WorkspaceService(db)
        user_id_str = current_user.get("user_id")
        user_id = UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str
        result = service.trigger_generation_cycle(workspace_id, user_id)
        background_tasks.add_task(run_generation_cycle, str(workspace_id))
        return result
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )
