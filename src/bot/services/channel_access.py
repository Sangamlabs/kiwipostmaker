import logging
from typing import Tuple
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

async def check_channel_permissions(bot: Bot, channel_id: str) -> Tuple[bool, str]:
    """
    Verify that the bot is an administrator in the destination channel
    with permissions to post messages (Page 4 of DX-Notes).
    """
    try:
        chat = await bot.get_chat(channel_id)
        bot_user = await bot.get_me()
        member = await bot.get_chat_member(channel_id, bot_user.id)

        # Check administrator status
        status = getattr(member, "status", "")
        if status not in {"administrator", "creator"}:
            return False, f"Bot is not an administrator in channel '{chat.title or channel_id}'."

        # Check can_post_messages permission if available
        can_post = getattr(member, "can_post_messages", None)
        if can_post is False:
            return False, f"Bot lacks 'Post Messages' permission in channel '{chat.title or channel_id}'."

        return True, "OK"
    except TelegramError as te:
        logger.error("Telegram API check failed for channel %s: %s", channel_id, te)
        return False, f"Failed to access channel: {te.message}"
    except Exception as exc:
        logger.exception("Unexpected error verifying channel permissions: %s", exc)
        return False, f"Permission check error: {str(exc)}"

async def verify_user_is_full_admin_or_owner(bot: Bot, channel_id: str, user_id: int) -> Tuple[bool, str, bool]:
    """
    Verify that the user is either the Channel Creator/Owner OR a Full-Power Administrator
    with 'can_promote_members' permission (power to add administrators).
    Returns (is_authorized, reason, is_creator).
    """
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        status = getattr(member, "status", "")

        # 1. Channel Owner / Creator (Full power)
        if status in {"creator", "owner"}:
            return True, "OK", True

        # 2. Administrator with 'can_promote_members' permission
        if status == "administrator":
            can_promote = getattr(member, "can_promote_members", False)
            if can_promote:
                return True, "OK", False
            return False, (
                "You are an administrator in this channel, but you do not have 'Add New Admins' "
                "(can_promote_members) authority. Only the channel Owner or a Full-Power Admin "
                "with 'Add New Admins' permission can connect or manage this channel."
            ), False

        return False, "You must be an administrator or owner in this channel.", False

    except TelegramError as te:
        logger.warning("Could not verify user permissions in channel %s: %s", channel_id, te)
        return False, f"Telegram error: {te.message}", False
    except Exception as exc:
        logger.exception("Error checking user permissions in channel %s: %s", channel_id, exc)
        return False, f"Verification error: {str(exc)}", False
