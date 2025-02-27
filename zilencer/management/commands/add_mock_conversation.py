from typing import Any, Dict, List

from django.core.management.base import BaseCommand

from zerver.actions.create_user import do_create_user
from zerver.actions.message_send import do_send_messages, internal_prep_stream_message
from zerver.actions.reactions import do_add_reaction
from zerver.actions.streams import bulk_add_subscriptions
from zerver.actions.user_settings import do_change_avatar_fields
from zerver.lib.emoji import get_emoji_data
from zerver.lib.streams import ensure_stream
from zerver.lib.upload import upload_avatar_image
from zerver.models import Message, UserProfile, get_realm


class Command(BaseCommand):
    help = """Add a mock conversation to the development environment.

Usage: ./manage.py add_mock_conversation

After running the script:

From browser (ideally on high resolution screen):
* Refresh to get the rendered tweet
* Check that the whale emoji reaction comes before the thumbs_up emoji reaction
* Remove the blue box (it's a box shadow on .selected_message .messagebox-content;
  inspecting the selected element will find it fairly quickly)
* Change the color of the stream to #a6c7e5
* Shrink screen till the mypy link only just fits
* Take screenshot that does not include the timestamps or bottom edge

From image editing program:
* Remove mute (and edit) icons from recipient bar
"""

    def set_avatar(self, user: UserProfile, filename: str) -> None:
        with open(filename, "rb") as f:
            upload_avatar_image(f, user, user)
        do_change_avatar_fields(user, UserProfile.AVATAR_FROM_USER, acting_user=None)

    def add_message_formatting_conversation(self) -> None:
        realm = get_realm("zulip")
        stream = ensure_stream(realm, "zulip features", acting_user=None)

        UserProfile.objects.filter(email__contains="stage").delete()
        starr = do_create_user(
            "1@stage.example.com", "password", realm, "Ada Starr", acting_user=None
        )
        self.set_avatar(starr, "static/images/characters/starr.png")
        fisher = do_create_user(
            "2@stage.example.com", "password", realm, "Bel Fisher", acting_user=None
        )
        self.set_avatar(fisher, "static/images/characters/fisher.png")
        twitter_bot = do_create_user(
            "3@stage.example.com",
            "password",
            realm,
            "Twitter Bot",
            bot_type=UserProfile.DEFAULT_BOT,
            acting_user=None,
        )
        self.set_avatar(twitter_bot, "static/images/features/twitter.png")

        bulk_add_subscriptions(
            realm, [stream], list(UserProfile.objects.filter(realm=realm)), acting_user=None
        )

        staged_messages: List[Dict[str, Any]] = [
            {
                "sender": starr,
                "content": "Hey @**Bel Fisher**, check out Zulip's Markdown formatting! "
                "You can have:\n* bulleted lists\n  * with sub-bullets too\n"
                "* **bold**, *italic*, and ~~strikethrough~~ text\n"
                "* LaTeX for mathematical formulas, both inline -- $$O(n^2)$$ -- and displayed:\n"
                "```math\n\\int_a^b f(t)\\, dt=F(b)-F(a)\n```",
            },
            {
                "sender": fisher,
                "content": "My favorite is the syntax highlighting for code blocks\n"
                "```python\ndef fib(n: int) -> int:\n    # returns the n-th Fibonacci number\n"
                "    return fib(n-1) + fib(n-2)\n```",
            },
            {
                "sender": starr,
                "content": "I think you forgot your base case there, Bel :laughing:\n"
                "```quote\n```python\ndef fib(n: int) -> int:\n    # returns the n-th Fibonacci number\n"
                "    return fib(n-1) + fib(n-2)\n```\n```",
            },
            {
                "sender": fisher,
                "content": "I'm also a big fan of inline link, tweet, video, and image previews. "
                "Check out this picture of Çet Whalin[](/static/images/features/whale.png)!",
            },
            {
                "sender": starr,
                "content": "I just set up a custom linkifier, "
                "so `#1234` becomes [#1234](github.com/zulip/zulip/1234), "
                "a link to the corresponding GitHub issue.",
            },
            {
                "sender": twitter_bot,
                "content": "https://twitter.com/gvanrossum/status/786661035637772288",
            },
            {
                "sender": fisher,
                "content": "Oops, the Twitter bot I set up shouldn't be posting here. Let me go fix that.",
            },
        ]

        messages = [
            internal_prep_stream_message(
                message["sender"],
                stream,
                "message formatting",
                message["content"],
            )
            for message in staged_messages
        ]

        message_ids = do_send_messages(messages)

        preview_message = Message.objects.get(
            id__in=message_ids, content__icontains="image previews"
        )
        whale = get_emoji_data(realm.id, "whale")
        do_add_reaction(starr, preview_message, "whale", whale.emoji_code, whale.reaction_type)

        twitter_message = Message.objects.get(id__in=message_ids, content__icontains="gvanrossum")
        # Setting up a twitter integration in dev is a decent amount of work. If you need
        # to update this tweet, either copy the format below, or send the link to the tweet
        # to chat.zulip.org and ask an admin of that server to get you the rendered_content.
        twitter_message.rendered_content = (
            "<p><a>https://twitter.com/gvanrossum/status/786661035637772288</a></p>\n"
            '<div class="inline-preview-twitter"><div class="twitter-tweet">'
            '<a><img class="twitter-avatar" '
            'src="https://pbs.twimg.com/profile_images/424495004/GuidoAvatar_bigger.jpg"></a>'
            "<p>Great blog post about Zulip's use of mypy: "
            "<a>http://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/</a></p>"
            "<span>- Guido van Rossum (@gvanrossum)</span></div></div>"
        )
        twitter_message.save(update_fields=["rendered_content"])

        # Put a short pause between the whale reaction and this, so that the
        # thumbs_up shows up second
        thumbs_up = get_emoji_data(realm.id, "thumbs_up")
        do_add_reaction(
            starr, preview_message, "thumbs_up", thumbs_up.emoji_code, thumbs_up.reaction_type
        )

    def handle(self, *args: Any, **options: str) -> None:
        self.add_message_formatting_conversation()
