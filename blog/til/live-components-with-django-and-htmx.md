---
title: "Live Components with Django and htmx"
meta-description: "Using Django and htmx to render components through server-sent events."
author: "Dylan Castillo"
date: "01/28/2024"
date-modified: last-modified
lightbox: true
fig-cap-location: margin
toc: true
toc-depth: 3
categories:
  - TIL
---

I discovered [`django-components`](https://github.com/EmilStenstrom/django-components/) late last year and I quickly realized it was the missing piece in my Django + htmx workflow. It made my developer experience so much better, that I even started contributing to it.

`django-components` lets you build components that combine HTML, JS, and CSS in a single place. Plus, it now lets you use components as views. This feature allows you to keep all the logic for a part of your application in one place, giving you great [locality of behavior](https://htmx.org/essays/locality-of-behaviour/).

A [click-to-load](https://htmx.org/examples/click-to-load/) component would look something like this:

```python
from django.core.paginator import Paginator
from django_components import component

from src.app.models import Contact


@component.register("click_to_load")
class ClickToLoadTableComponent(component.Component):
    template = """
        {% for contact in page_obj %}
            <tr>
                <td>{{ contact.id }}</td>
                <td>{{ contact.first_name }} {{ contact.last_name }}</td>
                <td>{{ contact.email }}</td>
                <td>{{ contact.status }}</td>
            </tr>
            {% if forloop.last and page_obj.has_next %}
                <tr id="replaceMe">
                    <td colspan="4">
                        <button
                            class='primary'
                            hx-get="{% url 'contacts' page=page_obj.next_page_number %}"
                            hx-target="#replaceMe"
                            hx-swap="outerHTML">
                            Load more...
                        </button>
                    </td>
                </tr>
            {% endif %}
        {% endfor %}
    """

    def get_context_data(self, page_obj, **kwargs):
        return {"page_obj": page_obj}

    def get(self, request, page, **kwargs):
        paginator = Paginator(Contact.objects.order_by("id"), 3)
        page_obj = paginator.get_page(page)
        context = {"page_obj": page_obj}
        return self.render_to_response(context)

```

You can use this component in any view using `{% component 'click_to_load' page_obj=page_obj %}` or render it outside of a view by adding it to `urls.py`:

```python
from django.urls import path

from src.components.click_to_load.table import ClickToLoadTableComponent

urlpatterns = [
    path(
        "contacts/<int:page>",
        ClickToLoadTableComponent.as_view(),
        name="contacts",
    ),
]

```

Short and sweet, just like the best things in life.

## Django Live Components

I thought it'd be fun to use the library for something it wasn't designed for: streaming component changes through server-sent events (SSE).

It took me a few hours and several reads of [Víðir's tutorial](https://valberg.dk/) to figure it out, but it worked. It's a bit hacky but all the pieces were there. I just had to find a way to put them together.

The code is available [here](https://github.com/dylanjcastillo/django-live-components).

I had a simple idea: set up a [Redis](https://redis.io/docs/interact/pubsub/) [pub/sub channel](https://redis.io/docs/interact/pubsub/) for server notifications. When the client loads the page, it subscribes to this notification channel. Each time the server publishes a new notification, the system reads it from the channel. Then, it renders the HTML and sends it to the client using Server-Sent Events (SSE).

First, you need a notification component, with a streaming view that updates the client whenever a new notification occurs, and a way to subscribe to new notifications sent from the server.

Here's what I came up with:

```python
import asyncio
import json
from typing import AsyncGenerator

import redis.asyncio as redis
from django.http import StreamingHttpResponse
from django.utils.decorators import classonlymethod
from django_components import component

r = redis.from_url("redis://localhost")


def sse_message(event_id: int, event: str, data: str) -> str:
    data = data.replace("\n", "")
    return f"id: {event_id}\n" f"event: {event}\n" f"data: {data.strip()}\n\n"


class NotificationComponent(component.Component):

    @classonlymethod
    def as_live_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view._is_coroutine = asyncio.coroutines._is_coroutine
        return view

    template = """
    <div style="color: {{color}};" role="alert">
        <span style="font-weight: bold;">{{ title }}</span> {{ message }}
    </div>
    """

    async def streaming_response(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async with r.pubsub() as pubsub:
            await pubsub.subscribe("notifications_channel")
            try:
                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1
                    )
                    if message is not None:
                        notification_data = json.loads(message["data"].decode())
                        sse_message_rendered = sse_message(
                            notification_data["id"],
                            "notification",
                            self.render(
                                {
                                    "title": notification_data["title"],
                                    "message": notification_data["message"],
                                    "color": notification_data["color"],
                                }
                            ),
                        )
                        yield sse_message_rendered
                    await asyncio.sleep(0.1)
            finally:
                await r.aclose()

    async def get(self, request, *args, **kwargs):
        return StreamingHttpResponse(
            streaming_content=self.streaming_response(),
            content_type="text/event-stream",
        )

```

And you should include this in your `urls.py`:

```python
from django.urls import path
from components.notification import NotificationComponent

urlpatterns = [
    path(
        "notification/",
        NotificationComponent.as_live_view(),
        name="stream_notification",
    ),
]

```

Then, you need a simple HTML template to show these notifications. I used the [htmx SSE extension](https://htmx.org/extensions/server-sent-events/) to handle the SSE connection on the client. This was my template:

```python
<!-- src/templates/index.html -->
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Django Live Components</title>
    </head>
    <body>
        <div hx-ext="sse"
             sse-connect="{% url 'stream_notification' %}"
             sse-swap="notification"></div>
        <script src="https://unpkg.com/htmx.org@1.9.10" integrity="sha384-D1Kt99CQMDuVetoL1lrYwg5t+9QdHe7NLX/SoJYkXDFfX37iInKRy5xLSi8nO7UC" crossorigin="anonymous">
        </script>
        <script src="https://unpkg.com/htmx.org/dist/ext/sse.js"></script>
    </body>
</html>

```

Finally, you need a script to simulate these server notifications:

```python
# random_notifications.py
import redis
import json
import random
import time

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_CHANNEL = "notifications_channel"

r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def create_random_notification():
    """Create a random notification message"""
    return {
        "id": random.randint(1, 1000),
        "title": "Notification " + str(random.randint(1, 100)),
        "message": "This is a random message " + str(random.randint(1, 100)),
        "color": random.choice(["blue", "green", "red", "black", "gray", "purple"]),
        "timestamp": time.ctime(),
    }


def publish_notification():
    """Publish a random notification to the Redis channel"""
    notification = create_random_notification()
    r.publish(REDIS_CHANNEL, json.dumps(notification))
    print(f"Published: {notification}")


if __name__ == "__main__":
    try:
        while True:
            publish_notification()
            time.sleep(3)
    except KeyboardInterrupt:
        print("Stopped notification publisher")

```

You can run Redis on Docker to run this script. It'll start adding notifications to the Redis channel, that you'll see flash on the page.

This was fun. I ended up using a similar pattern in [AItheneum](https://aitheneum.iwanalabs.com/).
