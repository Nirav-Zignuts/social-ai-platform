import os
from uuid import UUID

from fastapi import UploadFile, HTTPException
from slugify import slugify
from sqlalchemy.orm import Session

from app.api.v1.schemas.workspace_schema import (
    AIConfigurationUpsert,
    BusinessProfileUpsert,
    WorkspaceCreate,
    WorkspaceUpdate,
)
from app.common.messages import WorkspaceMessages, ErrorMessages
from app.common.responses import SuccessResponse
from app.models.ai_configuration import AIConfiguration
from app.models.business_profile import BusinessProfile
from app.models.knowledge_document import KnowledgeDocument
from app.models.workspace import Workspace
from app.repositories.workspace import (
    AIConfigurationRepository,
    BusinessProfileRepository,
    KnowledgeDocumentRepository,
    WorkspaceRepository,
)
from app.utils.cloudinary_service import CloudinaryService

ONBOARDING_STATUS_ORDER = {
    "workspace_created": 1,
    "profile_added": 2,
    "knowledge_added": 3,
    "ai_configured": 4,
    "completed": 5,
}

ALLOWED_FILE_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class WorkspaceService:
    def __init__(self, db: Session):
        self.db = db
        self.workspace_repo = WorkspaceRepository(db)
        self.business_repo = BusinessProfileRepository(db)
        self.ai_repo = AIConfigurationRepository(db)
        self.knowledge_repo = KnowledgeDocumentRepository(db)

    def _advance_onboarding_status(self, workspace: Workspace, new_minimum_status: str):
        current_weight = ONBOARDING_STATUS_ORDER.get(workspace.onboarding_status, 0)
        new_weight = ONBOARDING_STATUS_ORDER.get(new_minimum_status, 0)
        if new_weight > current_weight:
            workspace.onboarding_status = new_minimum_status

    def _generate_unique_slug(self, name: str) -> str:
        base_slug = slugify(name)
        slug = base_slug
        counter = 2
        while True:
            if not self.workspace_repo.get_by_slug(slug):
                return slug
            slug = f"{base_slug}-{counter}"
            counter += 1

    def _get_workspace_or_404(self, workspace_id: UUID, user_id: UUID) -> Workspace:
        workspace = self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail=ErrorMessages.WORKSPACE_NOT_FOUND)
        if workspace.owner_id != user_id:
            raise HTTPException(status_code=403, detail=ErrorMessages.FORBIDDEN)
        return workspace

    def create_workspace(self, payload: WorkspaceCreate, user_id: UUID) -> dict:
        slug = self._generate_unique_slug(payload.name)
        print(f"Generated slug: {slug}")  # Debugging line
        workspace = Workspace(
            owner_id=user_id,
            name=payload.name,
            slug=slug,
            timezone=payload.timezone,
            preferred_post_time=payload.preferred_post_time,
            require_human_approval=payload.require_human_approval,
        )
        print(f"Creating workspace: {workspace.name}")  # Debugging line
        self.workspace_repo.create(workspace)
        return {"workspace": workspace}

    def list_workspaces(self, user_id: UUID) -> dict:
        workspaces = self.workspace_repo.get_user_workspaces(user_id)
        return {"workspaces": workspaces}

    def get_workspace(self, workspace_id: UUID, user_id: UUID) -> dict:
        workspace = self._get_workspace_or_404(workspace_id, user_id)
        return {"workspace": workspace}

    def update_workspace(self, workspace_id: UUID, payload: WorkspaceUpdate, user_id: UUID) -> dict:
        workspace = self._get_workspace_or_404(workspace_id, user_id)
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(workspace, key, value)
        self.workspace_repo.update(workspace)
        return {"workspace": workspace}

    def upsert_business_profile(self, workspace_id: UUID, payload: BusinessProfileUpsert, user_id: UUID) -> dict:
        workspace = self._get_workspace_or_404(workspace_id, user_id)
        profile = self.business_repo.get_by_workspace_id(workspace.id)

        if profile:
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(profile, key, value)
        else:
            profile = BusinessProfile(workspace_id=workspace.id, **payload.model_dump())
            self.db.add(profile)

        self._advance_onboarding_status(workspace, "profile_added")
        self.db.commit()
        self.db.refresh(profile)
        return {"business_profile": profile}

    def get_business_profile(self, workspace_id: UUID, user_id: UUID) -> dict:
        workspace = self._get_workspace_or_404(workspace_id, user_id)
        profile = self.business_repo.get_by_workspace_id(workspace.id)
        if not profile:
            raise HTTPException(status_code=404, detail=ErrorMessages.BUSINESS_PROFILE_NOT_FOUND)
        return {"business_profile": profile}

    def upsert_ai_configuration(self, workspace_id: UUID, payload: AIConfigurationUpsert, user_id: UUID) -> dict:
        workspace = self._get_workspace_or_404(workspace_id, user_id)
        ai_config = self.ai_repo.get_by_workspace_id(workspace.id)

        if ai_config:
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(ai_config, key, value)
        else:
            ai_config = AIConfiguration(workspace_id=workspace.id, **payload.model_dump())
            self.db.add(ai_config)

        self._advance_onboarding_status(workspace, "ai_configured")
        self.db.commit()
        self.db.refresh(ai_config)
        return {"ai_configuration": ai_config}

    def get_ai_configuration(self, workspace_id: UUID, user_id: UUID) -> dict:
        workspace = self._get_workspace_or_404(workspace_id, user_id)
        ai_config = self.ai_repo.get_by_workspace_id(workspace.id)
        if not ai_config:
            raise HTTPException(status_code=404, detail=ErrorMessages.AI_CONFIG_NOT_FOUND)
        return {"ai_configuration": ai_config}

    async def upload_knowledge_document(self, workspace_id: UUID, file: UploadFile, user_id: UUID) -> dict:
        workspace = self._get_workspace_or_404(workspace_id, user_id)

        if file.content_type not in ALLOWED_FILE_TYPES:
            raise HTTPException(status_code=400, detail="Invalid file type. Only pdf, docx, txt allowed.")

        file_extension = ALLOWED_FILE_TYPES[file.content_type]

        # Check file size by seeking to end
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")

        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")

        doc = KnowledgeDocument(
            workspace_id=workspace.id,
            file_name=file.filename,
            file_type=file_extension,
            file_size_bytes=len(file_bytes),
            file_path="pending",
            uploaded_by=user_id,
            status="uploaded",
        )
        self.db.add(doc)
        self.db.flush()

        cloudinary = CloudinaryService()
        upload_public_id = f"{doc.id}.{file_extension}"

        try:
            upload_result = cloudinary.upload_document(
                file_bytes,
                folder=f"knowledge/{workspace.id}",
                public_id=upload_public_id,
            )

            doc.file_path = upload_result.secure_url
            doc.cloudinary_public_id = upload_result.public_id
            self._advance_onboarding_status(workspace, "knowledge_added")
            self.db.commit()
            self.db.refresh(doc)
            print(f"Document uploaded: {doc.id}")

            from app.knowledge.tasks import process_knowledge_document

            process_knowledge_document.delay(str(doc.id))

            return {"document": doc}
        except Exception as e:
            self.db.rollback()
            try:
                cloudinary.delete_resource(
                    f"knowledge/{workspace.id}/{upload_public_id}",
                    resource_type="raw",
                )
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

    def list_knowledge_documents(self, workspace_id: UUID, user_id: UUID) -> dict:
        workspace = self._get_workspace_or_404(workspace_id, user_id)
        docs = self.knowledge_repo.get_by_workspace_id(workspace.id)
        return {"documents": docs}

    def delete_knowledge_document(self, workspace_id: UUID, document_id: UUID, user_id: UUID) -> None:
        workspace = self._get_workspace_or_404(workspace_id, user_id)
        doc = self.knowledge_repo.get_by_id_and_workspace(document_id, workspace.id)

        if not doc:
            raise HTTPException(status_code=404, detail=ErrorMessages.RESOURCE_NOT_FOUND)

        # Cleanup ChromaDB vectors
        from app.knowledge.vectorstore import delete_document_vectors
        delete_document_vectors(str(workspace.id), str(doc.id))

        cloudinary = CloudinaryService()
        public_id = doc.cloudinary_public_id or cloudinary.resolve_public_id(
            secure_url=doc.file_path,
        )
        if public_id:
            cloudinary.delete_resource(public_id, resource_type="raw")

        self.knowledge_repo.delete(doc)

    def trigger_generation_cycle(self, workspace_id: UUID, user_id: UUID) -> dict:
        print(f"Triggering generation cycle for workspace: {workspace_id}")
        workspace = self._get_workspace_or_404(workspace_id, user_id)
        from app.services.generation_tasks import run_generation_cycle
        print(f"Running generation cycle for workspace: {workspace.id}")
        task = run_generation_cycle.delay(str(workspace.id))
        return {"generation_cycle_id": task.id, "status": "queued"}
