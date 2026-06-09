User Guide
==========

RESPX is a mock router, [capturing](#mock-httpx) requests sent by `HTTPX`, [mocking](#mocking-responses) their responses.

Inspired by the flexible query API of the [Django](https://www.djangoproject.com/) ORM, requests are filtered and matched against routes and their request [patterns](../api/#patterns) and [lookups](../api/#lookups).

Request [patterns](../api/#patterns) are _bits_ of the request, like `host` `method` `path` etc, with given [lookup](../api/#lookups) values, combined using _bitwise_ [operators](../api/#operators) to form a `Route`, i.e. `respx.route(path__regex=...)`

A captured request, [matching](#routing-requests) a `Route`, resolves to a [mocked](#mock-a-response) `httpx.Response`, or triggers a given [side effect](#mock-with-a-side-effect). To skip mocking a specific request, a route can be marked to [pass through](#pass-through).

Mock HTTPX
----------

To patch `HTTPX`, and activate the RESPX router, use the `respx.mock` decorator/context manager, or the `respx_mock` _pytest_ fixture.

### Using the Decorator

`import httpx import respx  @respx.mock def test_decorator():     my_route = respx.get("https://example.org/")     response = httpx.get("https://example.org/")     assert my_route.called     assert response.status_code == 200`

### Using the Context Manager

`import httpx import respx  def test_ctx_manager():     with respx.mock:         my_route = respx.get("https://example.org/")         response = httpx.get("https://example.org/")         assert my_route.called         assert response.status_code == 200`

### Using the pytest Fixture

`import httpx  def test_fixture(respx_mock):     my_route = respx_mock.get("https://example.org/")     response = httpx.get("https://example.org/")     assert my_route.called     assert response.status_code == 200`

### Router Settings

The RESPX router can be configured with built-in assertion checks and an _optional_ [base URL](#base-url).

By configuring, an isolated router is created, and settings are _locally_ bound to the routes added.

Either of the decorator, context manager and fixture takes the same configuration arguments.

> See router [configuration](../api/#configuration) reference for more details.

**Configure the Decorator**

When decorating a test case with configured router settings, the test function will receive the router instance as a `respx_mock` argument.

`@respx.mock(...) def test_something(respx_mock):     ...`

**Configure the Context Manager**

When passing settings to the context manager, the configured router instance will be _yielded_.

`with respx.mock(...) as respx_mock:     ...`

**Configure the Fixture**

To configure the router when using the `pytest` fixture, decorate the test case with the `respx` _pytest marker_.

`@pytest.mark.respx(...) def test_something(respx_mock):     ...`

#### Base URL

When adding a lot of routes, sharing the same domain/prefix, you can configure the router with a `base_url` to be used for added routes.

`import httpx import respx  from httpx import Response  @respx.mock(base_url="https://example.org/api/") async def test_something(respx_mock):     async with httpx.AsyncClient(base_url="https://example.org/api/") as client:         respx_mock.get("/baz/").mock(return_value=Response(200, text="Baz"))         response = await client.get("/baz/")         assert response.text == "Baz"`

#### Assert all Mocked

By default, asserts that all sent and captured `HTTPX` requests are routed and mocked.

`@respx.mock(assert_all_mocked=True) def test_something(respx_mock):     response = httpx.get("https://example.org/")  # Not mocked, will raise`

If _disabled_, all non-routed requests will be auto-mocked with status code `200`.

`@respx.mock(assert_all_mocked=False) def test_something(respx_mock):     response = httpx.get("https://example.org/")  # Will auto-mock     assert response.status_code == 200`

#### Assert all Called

By default, asserts that all added and mocked routes were called when exiting _decorated_ test case, _context manager_ scope or exiting a text case using the pytest fixture.

`@respx.mock(assert_all_called=True) def test_something(respx_mock):     respx_mock.get("https://example.org/")     respx_mock.get("https://some.url/")  # Not called, will fail the test      response = httpx.get("https://example.org/")`

`@respx.mock(assert_all_called=False) def test_something(respx_mock):     respx_mock.get("https://example.org/")     respx_mock.get("https://some.url/")  # Not called, yet not asserted      response = httpx.get("https://example.org/")     assert response.status_code == 200`

* * *

Routing Requests
----------------

The easiest way to add routes is to use the [HTTP Method](#http-method-helpers) helpers.

For full control over the request pattern matching, use the [route](#route-api) API.

Routes are matched and routed in _added order_. This means that routes with more specific patterns should to be added earlier than the ones with less "details".

### HTTP Method Helpers

Each HTTP method has a helper function (`get`, `options`, `head`, `post`, `put`, `patch`, `delete`), _shortcutting_ the [route](#route-api) API.

`my_route = respx.get("https://example.org/", params={"foo": "bar"}) response = httpx.get("https://example.org/", params={"foo": "bar"}) assert my_route.called assert response.status_code == 200`

> See [.get(), .post(), ...](../api/#get-post) helpers reference for more details.

### Route API

#### Patterns

With the `route` API, you define a combined pattern to match, capturing a sent request.

`my_route = respx.route(method="GET", host="example.org", path="/foobar/") response = httpx.get("https://example.org/foobar/") assert my_route.called assert response.status_code == 200`

> See [.route()](../api/#route) reference for more details.

#### Lookups

Each [pattern](../api/#patterns) has a _default_ lookup. To specify what [lookup](../api/#lookups) to use, add a `__<lookup>` suffix.

`respx.route(method__in=["PUT", "PATCH"])`

#### Combining Patterns

For even more flexibility, you can define combined patterns using the [M()](../api/#m) _object_, together with bitwise [operators](../api/#operators) (`&`, `|,` `~`), creating a reusable pattern.

`hosts_pattern = M(host="example.org") | M(host="example.com") my_route = respx.route(hosts_pattern, method="GET", path="/foo/")  response = httpx.get("http://example.org/foo/") assert response.status_code == 200 assert my_route.called  response = httpx.get("https://example.com/foo/") assert response.status_code == 200 assert my_route.call_count == 2`

NOTE

`M(url="//example.org/foobar/")` is **equal** to `M(host="example.org") & M(path="/foobar/")`

### Named Routes

Routes can be _named_ when added, and later accessed through the `respx.routes` mapping.

This is useful when a route is added _outside_ the test case, _e.g._ access or assert route calls.

`import httpx import respx  # Added somewhere else respx.get("https://example.org/", name="home")  @respx.mock def test_route_call():     httpx.get("https://example.org/")     assert respx.routes["home"].called     assert respx.routes["home"].call_count == 1      last_home_response = respx.routes["home"].calls.last.response     assert last_home_response.status_code == 200`

### Reusable Routers

As described under [settings](#router-settings), an isolated router is created when calling `respx.mock(...)`.

Isolated routers are useful when mocking multiple remote APIs, allowing grouped routes per API, and to be mocked individually or stacked for reuse across tests.

Use the router instance as decorator or context manager to patch `HTTPX` and activate the routes.

`import httpx import respx  api_mock = respx.mock(base_url="https://api.foo.bar/", assert_all_called=False) api_mock.get("/baz/", name="baz").mock(     return_value=httpx.Response(200, json={"name": "baz"}), ) ...  @api_mock def test_decorator():     response = httpx.get("https://api.foo.bar/baz/")     assert response.status_code == 200     assert response.json() == {"name": "baz"}     assert api_mock["baz"].called  def test_ctx_manager():     with api_mock:         ...`

Catch-all

Add a _catch-all_ route last as a fallback for any non-matching request, e.g. `api_mock.route().respond(404)`.

NOTE

Named routes in a _reusable router_ can be directly accessed via `my_mock_router[<route name>]`

### Route with an App

As an alternative one can route and mock responses with an `app` by passing either a `respx.WSGIHandler` or `respx.ASGIHandler` as side effect when mocking.

**Sync App Example**

`import httpx import respx  from flask import Flask  app = Flask("foobar")  @app.route("/baz/") def baz():     return {"ham": "spam"}  @respx.mock(base_url="https://foo.bar/") def test_baz(respx_mock):     app_route = respx_mock.route().mock(side_effect=WSGIHandler(app))     response = httpx.get("https://foo.bar/baz/")     assert response.json() == {"ham": "spam"}     assert app_route.called`

**Async App Example**

`import httpx import respx  from starlette.applications import Starlette from starlette.responses import JSONResponse from starlette.routing import Route  async def baz(request):     return JSONResponse({"ham": "spam"})  app = Starlette(routes=[Route("/baz/", baz)])  @respx.mock(base_url="https://foo.bar/") async def test_baz(respx_mock):     app_route = respx_mock.route().mock(side_effect=ASGIHandler(app))     response = await httpx.AsyncClient().get("https://foo.bar/baz/")     assert response.json() == {"ham": "spam"}     assert app_route.called`

* * *

Mocking Responses
-----------------

To mock a [route](#routing-requests) response, use `<route>.mock(...)` to either...

*   set the `httpx.Response` to be [returned](#mock-a-response).
*   set a [side effect](#mock-with-a-side-effect) to be triggered.

The route's mock interface is inspired by pythons built-in `Mock()` object, e.g. `side_effect` has precedence over `return_value`, side effects can either be functions, exceptions or an iterable, raising `StopIteration` when "exhausted" etc.

### Mock a Response

Create a mocked `HTTPX` [Response](../api/#response) object and pass it as `return_value`.

`respx.get("https://example.org/").mock(return_value=Response(204))`

> See [.mock()](../api/#mock) reference for more details.

You can also use the `<route>.return_value` _setter_.

`route = respx.get("https://example.org/") route.return_value = Response(200, json={"foo": "bar"})`

### Mock with a Side Effect

RESPX _side effects_ works just like the python `Mock` side effects.

It can either be a [function](#functions) to call, an [exception](#exceptions) to raise, or an [iterable](#iterable) of responses/exceptions to respond with in order, for repeated requests.

`respx.get("https://example.org/").mock(side_effect=...)`

You can also use the `<route>.side_effect` _setter_.

`route = respx.get("https://example.org/") route.side_effect = ...`

#### Functions

Function _side effects_ will be called with the _captured_ `request` argument, and should either...

*   return a mocked [Response](../api/#response).
*   raise an `Exception` to simulate a request error.
*   return `None` to treat the route as a _non-match_, continuing testing further routes.
*   return the input `Request` to [pass through](#pass-through).

`import httpx import respx  def my_side_effect(request):     return httpx.Response(201)  @respx.mock def test_side_effect():     respx.post("https://example.org/").mock(side_effect=my_side_effect)      response = httpx.post("https://example.org/")     assert response.status_code == 201`

Optionally, a side effect can include a `route` argument for cases where call stats, or modifying the route within the side effect, is needed.

`import httpx import respx  def my_side_effect(request, route):     return httpx.Response(201, json={"id": route.call_count + 1})  @respx.mock def test_side_effect():     respx.post("https://example.org/").mock(side_effect=my_side_effect)      response = httpx.post("https://example.org/")     assert response.json() == {"id": 1}      response = httpx.post("https://example.org/")     assert response.json() == {"id": 2}`

If any of the route patterns are using a [regex lookup](../api/#regex), containing _named groups_, the regex groups will be passed as _kwargs_ to the _side effect_.

`import httpx import respx  def my_side_effect(request, slug):     return httpx.Response(200, json={"slug": slug})  @respx.mock def test_side_effect_kwargs():     route = respx.route(url__regex=r"https://example.org/(?P<slug>\w+)/")     route.side_effect = my_side_effect      response = httpx.get("https://example.org/foobar/")     assert response.status_code == 200     assert response.json() == {"slug": "foobar"}`

A route can even _decorate_ the function to be used as _side effect_.

`import httpx import rexpx  @respx.route(url__regex=r"https://example.org/(?P<user>\w+)/", name="user") def user_api(request, user):     return httpx.Response(200, json={"user": user})  @respx.mock def test_user_api():     response = httpx.get("https://example.org/lundberg/")     assert response.status_code == 200     assert response.json() == {"user": "lundberg"}     assert respx.routes["user"].called`

#### Exceptions

To simulate a request error, pass a [httpx.HTTPError](https://www.python-httpx.org/exceptions/#the-exception-hierarchy) _subclass_, or any `Exception` as _side effect_.

`import httpx import respx  @respx.mock def test_connection_error():     respx.get("https://example.org/").mock(side_effect=httpx.ConnectError)      with pytest.raises(httpx.ConnectError):         httpx.get("https://example.org/")`

#### Iterable

If the side effect is an _iterable_, each repeated request will get the _next_ [Response](../api/#response) returned, or [exception](#exceptions) raised, from the iterable.

`import httpx import respx  @respx.mock def test_stacked_responses():     route = respx.get("https://example.org/")     route.side_effect = [         httpx.Response(404),         httpx.Response(200),     ]      response1 = httpx.get("https://example.org/")     response2 = httpx.get("https://example.org/")      assert response1.status_code == 404     assert response2.status_code == 200     assert route.call_count == 2`

Like python `Mock` side effects, `StopIteration` will be raised once the iterable is _exhausted_. A more practical use case is to have the last entry infinitely repeated, which can be done by utilizing `itertools`.

`from itertools import chain, repeat import httpx import respx  @respx.mock def test_stacked_responses():     respx.post("https://example.org/").mock(         side_effect=chain(             [httpx.Response(201)],             repeat(httpx.Response(200)),         )     )      response1 = httpx.post("https://example.org/")     response2 = httpx.post("https://example.org/")     response3 = httpx.post("https://example.org/")      assert response1.status_code == 201     assert response2.status_code == 200     assert response3.status_code == 200`

### Shortcuts

#### Respond

For convenience, `<route>.respond(...)` can be used as a shortcut to `return_value`.

`respx.post("https://example.org/").respond(201)`

> See [.respond()](../api/#respond) reference for more details.

#### Modulo

For simple mocking, a quick way is to use the python modulo (`%`) operator to mock the response.

The _right-hand_ modulo argument can either be ...

An `int` representing the `status_code` to mock:

`respx.get("https://example.org/") % 204  response = httpx.get("https://example.org/") assert response.status_code == 204`

A `dict` used as _kwargs_ to create a mocked `HTTPX` [Response](../api/#response), with status code `200` by default:

`respx.get("https://example.org/") % dict(json={"foo": "bar"})  response = httpx.get("https://example.org/") assert response.status_code == 200 assert response.json() == {"foo": "bar"}`

A `HTTPX` [Response](../api/#response) object:

`respx.get("https://example.org/") % Response(418)  response = httpx.get("https://example.org/") assert response.status_code == httpx.codes.IM_A_TEAPOT`

Rollback
--------

When exiting a [decorated](#using-the-decorator) test case, or [context manager](#using-the-context-manager), the routes and their mocked values, _i.e._ `return_value` and `side_effect`, will be _rolled back_ and restored to their initial state.

This means that you can safely modify existing routes, or add new ones, _within_ a test case, without affecting other tests that are using the same router.

`import httpx import respx  # Initial routes mock_router = respx.mock(base_url="https://example.org") mock_router.get(path__regex="/user/(?P<pk>\d+)/", name="user") % 404 ...  @mock_router def test_user_exists():     # This change will be rolled back after this test case     mock_router["user"].return_value = httpx.Response(200)      response = httpx.get("https://example.org/user/123/")     assert response.status_code == 200  @mock_router def test_user_not_found():     response = httpx.get("https://example.org/user/123/")     assert response.status_code == 404`

* * *

Pass Through
------------

If you want a route to _not_ capture and mock a request response, use `.pass_through()`.

`import httpx import respx  @respx.mock def test_remote_response():     respx.route(host="localhost").pass_through()     response = httpx.get("http://localhost:8000/")  # response from server`

> See [.pass\_through()](../api/#pass_through) reference for more details.

* * *

Mock without patching HTTPX
---------------------------

If you don't _need_ to patch `HTTPX`, use `httpx.MockTransport` with a RESPX router as handler, when instantiating your client.

`import httpx import respx  router = respx.Router() router.post("https://example.org/") % 404  def test_client():     mock_transport = httpx.MockTransport(router.handler)     with httpx.Client(transport=mock_transport) as client:         response = client.post("https://example.org/")         assert response.status_code == 404  def test_client():     mock_transport = httpx.MockTransport(router.async_handler)     with httpx.AsyncClient(transport=mock_transport) as client:         ...`

NOTE

To assert all routes is called, you'll need to trigger `<router>.assert_all_called()` manually, e.g. in a test case or after yielding the router in a _pytest_ fixture, since there's no auto post assertion done like when using [respx.mock](#assert-all-called).

Hint

You can use `RESPX` not only to mock out `HTTPX`, but actually mock any library using `HTTP Core` transports.

* * *

Call History
------------

The `respx` API includes a `.calls` object, containing captured (`request`, `response`) named tuples and MagicMock's _bells and whistles_, i.e. `call_count`, `assert_called` etc.

### Asserting calls

`assert respx.calls.called assert respx.calls.call_count == 1  respx.calls.assert_called() respx.calls.assert_not_called() respx.calls.assert_called_once()`

### Retrieving mocked calls

A matched and mocked `Call` can be retrieved from call history, by either unpacking...

`request, response = respx.calls.last request, response = respx.calls[-2]  # by call order`

...or by accessing `request` or `response` directly...

`last_request = respx.calls.last.request assert json.loads(last_request.content) == {"foo": "bar"}  last_response = respx.calls.last.response assert last_response.status_code == 200`

### Local route calls

Each `Route` object has its own `.calls`, along with `.called` and `.call_count` shortcuts.

`import httpx import respx  @respx.mock def test_route_call_stats():     route = respx.post("https://example.org/baz/") % 201     httpx.post("https://example.org/baz/")      assert route.calls.last.request.url.path == "/baz/"     assert route.calls.last.response.status_code == 201      assert route.called     assert route.call_count == 1      route.calls.assert_called_once()`

### Reset History

The call history will automatically _reset_ when exiting mocked context, i.e. leaving a [decorated](#using-the-decorator) test case, or [context manager](#using-the-context-manager) scope.

To manually _reset_ call stats during a test case, use `respx.reset()` or `<your_router>.reset()`.

`import httpx import respx  @respx.mock def test_reset():     respx.post("https://foo.bar/baz/")     httpx.post("https://foo.bar/baz/")      assert respx.calls.call_count == 1     respx.calls.assert_called_once()      respx.reset()      assert len(respx.calls) == 0     assert respx.calls.call_count == 0     respx.calls.assert_not_called()`

