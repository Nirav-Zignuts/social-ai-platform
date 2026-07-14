"""
Product email templates — table-based HTML for client compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from app.core.config import settings
from app.core.enums import NotificationType


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html_body: str
    text_body: str


# Brand tokens (inline for email clients — no external CSS)
_BG = "#F4F5F7"
_CARD = "#FFFFFF"
_INK = "#0F172A"
_MUTED = "#64748B"
_BORDER = "#E2E8F0"
_ACCENT = "#0D9488"  # teal — distinct from purple AI cliché
_ACCENT_TEXT = "#FFFFFF"
_FOOTER = "#94A3B8"


def _app_name() -> str:
    return settings.APP_NAME or "AI Marketing Platform"


def _frontend() -> str:
    return settings.FRONTEND_URL.rstrip("/")


def _button(url: str, label: str) -> str:
    safe_url = escape(url, quote=True)
    safe_label = escape(label)
    return f"""
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0 8px 0;">
        <tr>
          <td align="center" bgcolor="{_ACCENT}" style="border-radius:8px;">
            <a href="{safe_url}"
               style="display:inline-block;padding:14px 28px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;font-weight:600;line-height:1.2;color:{_ACCENT_TEXT};text-decoration:none;border-radius:8px;">
              {safe_label}
            </a>
          </td>
        </tr>
      </table>
    """


def _detail_row(label: str, value: str) -> str:
    return f"""
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid {_BORDER};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:13px;color:{_MUTED};width:38%;vertical-align:top;">
          {escape(label)}
        </td>
        <td style="padding:10px 0;border-bottom:1px solid {_BORDER};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:14px;color:{_INK};vertical-align:top;">
          {escape(value)}
        </td>
      </tr>
    """


def render_layout(
    *,
    preheader: str,
    eyebrow: str,
    title: str,
    greeting: str,
    body_html: str,
    cta_url: str | None = None,
    cta_label: str | None = None,
    secondary_html: str = "",
    footer_note: str = "You’re receiving this because you have an account with us.",
) -> str:
    app = escape(_app_name())
    year = __import__("datetime").datetime.now().year
    cta_block = _button(cta_url, cta_label) if cta_url and cta_label else ""
    pre = escape(preheader)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light" />
  <title>{escape(title)}</title>
</head>
<body style="margin:0;padding:0;background:{_BG};">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">
    {pre}
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{_BG};padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;">
          <tr>
            <td style="padding:0 8px 20px 8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:13px;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;color:{_INK};">
              {app}
            </td>
          </tr>
          <tr>
            <td bgcolor="{_CARD}" style="background:{_CARD};border:1px solid {_BORDER};border-radius:12px;padding:36px 32px;">
              <p style="margin:0 0 8px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:12px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{_ACCENT};">
                {escape(eyebrow)}
              </p>
              <h1 style="margin:0 0 20px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:24px;line-height:1.3;font-weight:700;color:{_INK};">
                {escape(title)}
              </h1>
              <p style="margin:0 0 16px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.6;color:{_INK};">
                {escape(greeting)}
              </p>
              <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.65;color:{_MUTED};">
                {body_html}
              </div>
              {cta_block}
              {secondary_html}
            </td>
          </tr>
          <tr>
            <td style="padding:24px 8px 0 8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:12px;line-height:1.5;color:{_FOOTER};text-align:left;">
              <p style="margin:0 0 8px 0;">{escape(footer_note)}</p>
              <p style="margin:0;">© {year} {app}. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _text_block(
    *,
    greeting: str,
    paragraphs: list[str],
    cta_label: str | None = None,
    cta_url: str | None = None,
    footer: str = "You’re receiving this because you have an account with us.",
) -> str:
    lines = [greeting, ""]
    lines.extend(paragraphs)
    if cta_url and cta_label:
        lines.extend(["", f"{cta_label}:", cta_url])
    lines.extend(["", "--", _app_name(), footer])
    return "\n".join(lines)


def verification_email(*, full_name: str, verification_link: str) -> RenderedEmail:
    name = full_name.strip() or "there"
    subject = f"Verify your email — {_app_name()}"
    body_html = f"""
      <p style="margin:0 0 12px 0;color:{_MUTED};">
        Thanks for signing up. Confirm your email to activate your account and start building your content workspace.
      </p>
      <p style="margin:0;color:{_MUTED};">
        This link expires for security. If you didn’t create an account, you can safely ignore this message.
      </p>
    """
    html = render_layout(
        preheader="Confirm your email to activate your account.",
        eyebrow="Welcome",
        title="Verify your email address",
        greeting=f"Hi {name},",
        body_html=body_html,
        cta_url=verification_link,
        cta_label="Verify email",
        secondary_html=f"""
          <p style="margin:24px 0 0 0;font-size:12px;line-height:1.5;color:{_FOOTER};word-break:break-all;">
            Or copy this link:<br/>
            <a href="{escape(verification_link, quote=True)}" style="color:{_ACCENT};">{escape(verification_link)}</a>
          </p>
        """,
        footer_note="If you didn’t create an account, you can ignore this email.",
    )
    text = _text_block(
        greeting=f"Hi {name},",
        paragraphs=[
            "Thanks for signing up. Confirm your email to activate your account and start building your content workspace.",
            "If you didn’t create an account, you can safely ignore this message.",
        ],
        cta_label="Verify email",
        cta_url=verification_link,
        footer="If you didn’t create an account, you can ignore this email.",
    )
    return RenderedEmail(subject=subject, html_body=html, text_body=text)


def post_ready_for_review_email(
    *,
    full_name: str,
    review_link: str,
    workspace_name: str | None = None,
) -> RenderedEmail:
    name = full_name.strip() or "there"
    subject = f"A new post is ready for review — {_app_name()}"
    context = (
        f" in <strong style=\"color:{_INK};\">{escape(workspace_name)}</strong>"
        if workspace_name
        else ""
    )
    body_html = f"""
      <p style="margin:0 0 12px 0;color:{_MUTED};">
        A new AI-generated post{context} is waiting for your approval before it goes live.
      </p>
      <p style="margin:0;color:{_MUTED};">
        Review the caption, image, and timing — approve, edit, or regenerate as needed.
      </p>
    """
    html = render_layout(
        preheader="A new post is waiting for your approval.",
        eyebrow="Review required",
        title="Your post is ready to review",
        greeting=f"Hi {name},",
        body_html=body_html,
        cta_url=review_link,
        cta_label="Review post",
    )
    text = _text_block(
        greeting=f"Hi {name},",
        paragraphs=[
            f"A new AI-generated post{f' in {workspace_name}' if workspace_name else ''} is waiting for your approval before it goes live.",
            "Review the caption, image, and timing — approve, edit, or regenerate as needed.",
        ],
        cta_label="Review post",
        cta_url=review_link,
    )
    return RenderedEmail(subject=subject, html_body=html, text_body=text)


def instagram_token_expired_email(
    *,
    full_name: str,
    settings_link: str,
    workspace_name: str | None = None,
) -> RenderedEmail:
    name = full_name.strip() or "there"
    subject = f"Reconnect Instagram to keep publishing — {_app_name()}"
    ws = f" for <strong style=\"color:{_INK};\">{escape(workspace_name)}</strong>" if workspace_name else ""
    body_html = f"""
      <p style="margin:0 0 12px 0;color:{_MUTED};">
        Your Instagram connection{ws} has expired or been revoked. Scheduled posts can’t publish until you reconnect.
      </p>
      <p style="margin:0;color:{_MUTED};">
        This only takes a minute — reconnect so your content calendar stays on track.
      </p>
    """
    html = render_layout(
        preheader="Your Instagram connection expired. Reconnect to resume publishing.",
        eyebrow="Action needed",
        title="Reconnect your Instagram account",
        greeting=f"Hi {name},",
        body_html=body_html,
        cta_url=settings_link,
        cta_label="Reconnect Instagram",
    )
    text = _text_block(
        greeting=f"Hi {name},",
        paragraphs=[
            f"Your Instagram connection{f' for {workspace_name}' if workspace_name else ''} has expired or been revoked. Scheduled posts can’t publish until you reconnect.",
            "This only takes a minute — reconnect so your content calendar stays on track.",
        ],
        cta_label="Reconnect Instagram",
        cta_url=settings_link,
    )
    return RenderedEmail(subject=subject, html_body=html, text_body=text)


def publish_failed_email(
    *,
    full_name: str,
    review_link: str,
    error_reason: str | None = None,
    workspace_name: str | None = None,
) -> RenderedEmail:
    name = full_name.strip() or "there"
    subject = f"A scheduled post failed to publish — {_app_name()}"
    reason = (error_reason or "Unknown error from Instagram").strip()
    ws = f" in <strong style=\"color:{_INK};\">{escape(workspace_name)}</strong>" if workspace_name else ""
    body_html = f"""
      <p style="margin:0 0 16px 0;color:{_MUTED};">
        We tried publishing a scheduled post{ws} several times, but Instagram rejected it. The post is marked as failed so you can review and take action.
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 4px 0;background:#F8FAFC;border:1px solid {_BORDER};border-radius:8px;padding:4px 16px;">
        {_detail_row("Status", "Publish failed")}
        {_detail_row("Reason", reason[:400])}
      </table>
      <p style="margin:16px 0 0 0;color:{_MUTED};">
        Open the post to check the creative, reconnect Instagram if needed, then republish or regenerate.
      </p>
    """
    html = render_layout(
        preheader="A scheduled Instagram post failed after multiple attempts.",
        eyebrow="Publishing issue",
        title="We couldn’t publish your post",
        greeting=f"Hi {name},",
        body_html=body_html,
        cta_url=review_link,
        cta_label="View post",
    )
    text = _text_block(
        greeting=f"Hi {name},",
        paragraphs=[
            f"We tried publishing a scheduled post{f' in {workspace_name}' if workspace_name else ''} several times, but Instagram rejected it.",
            f"Reason: {reason[:400]}",
            "Open the post to check the creative, reconnect Instagram if needed, then republish or regenerate.",
        ],
        cta_label="View post",
        cta_url=review_link,
    )
    return RenderedEmail(subject=subject, html_body=html, text_body=text)


def generic_notification_email(
    *,
    full_name: str,
    subject: str,
    message: str,
    cta_url: str | None = None,
    cta_label: str = "Open in app",
    eyebrow: str = "Update",
    title: str | None = None,
) -> RenderedEmail:
    name = full_name.strip() or "there"
    heading = title or subject
    body_html = f'<p style="margin:0;color:{_MUTED};">{escape(message)}</p>'
    html = render_layout(
        preheader=message[:120],
        eyebrow=eyebrow,
        title=heading,
        greeting=f"Hi {name},",
        body_html=body_html,
        cta_url=cta_url,
        cta_label=cta_label if cta_url else None,
    )
    text = _text_block(
        greeting=f"Hi {name},",
        paragraphs=[message],
        cta_label=cta_label if cta_url else None,
        cta_url=cta_url,
    )
    return RenderedEmail(subject=subject, html_body=html, text_body=text)


def render_notification_email(
    *,
    notification_type: NotificationType | str,
    full_name: str,
    payload: dict,
    subject: str,
) -> RenderedEmail:
    """Map notification types to product email templates."""
    try:
        ntype = (
            notification_type
            if isinstance(notification_type, NotificationType)
            else NotificationType(notification_type)
        )
    except ValueError:
        ntype = None

    message = payload.get("message") or "You have a new notification."
    review_link = payload.get("review_link")
    settings_link = payload.get("settings_link")
    workspace_name = payload.get("workspace_name")
    error_reason = payload.get("error_reason")

    if ntype == NotificationType.POST_READY_FOR_REVIEW and review_link:
        return post_ready_for_review_email(
            full_name=full_name,
            review_link=review_link,
            workspace_name=workspace_name,
        )
    if ntype == NotificationType.INSTAGRAM_TOKEN_EXPIRED and settings_link:
        return instagram_token_expired_email(
            full_name=full_name,
            settings_link=settings_link,
            workspace_name=workspace_name,
        )
    if ntype == NotificationType.POST_PUBLISH_FAILED and review_link:
        return publish_failed_email(
            full_name=full_name,
            review_link=review_link,
            error_reason=error_reason,
            workspace_name=workspace_name,
        )

    cta_url = review_link or settings_link
    cta_label = "Open settings" if settings_link and not review_link else "Open in app"
    return generic_notification_email(
        full_name=full_name,
        subject=subject,
        message=message,
        cta_url=cta_url,
        cta_label=cta_label,
    )
