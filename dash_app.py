import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output
from flask import session

# ------------------------ Dash App ------------------------
dash_app = dash.Dash(
    __name__,
    requests_pathname_prefix="/dash/",  # URL prefix pour Dash
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)

dash_app.title = "DataIA Dashboard"
server = dash_app.server  # sera relié à Flask via DispatcherMiddleware

# ------------------------ Layouts ------------------------
def sidebar():
    return html.Div(
        className="sidebar",
        children=[
            html.H2("DataIA", className="logo"),
            html.Hr(),
            html.Ul([
                html.Li(dcc.Link("📊 Dashboard", href="/dash/")),
                html.Li(dcc.Link("🤖 AI Chat", href="/dash/chat")),
                html.Li(dcc.Link("📁 Data", href="/dash/data")),
                html.Li(dcc.Link("🚪 Logout", href="/logout")),
            ], className="menu"),
        ]
    )

def dashboard_home():
    return html.Div([
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Users"), html.H2("1,245")])), md=4),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Files"), html.H2("87")])), md=4),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("AI Requests"), html.H2("3,412")])), md=4),
        ])
    ])

def chat_page():
    return dbc.Card(
        dbc.CardBody([
            html.H4("🤖 AI Chat"),
            dcc.Textarea(
                id="user-input",
                placeholder="Ask the AI something...",
                style={"width": "100%", "height": "120px"}
            ),
            html.Br(),
            dbc.Button("Send", color="primary", id="send-btn"),
            html.Hr(),
            html.Div(id="ai-output")
        ])
    )

def data_page():
    return html.Div([
        html.H4("📁 Data Upload"),
        html.P("CSV / Excel upload coming soon...")
    ])

def main_layout(content):
    return html.Div(
        className="dash-wrapper",
        children=[
            sidebar(),
            html.Div(
                className="main",
                children=[
                    html.Div(
                        className="topbar",
                        children=[
                            html.H3("Welcome to DataIA"),
                            html.Span(f"👤 {session.get('user_nom', '')}")
                        ]
                    ),
                    html.Div(className="content", children=content)
                ]
            )
        ]
    )

# ------------------------ Root Layout ------------------------
dash_app.layout = html.Div([
    dcc.Location(id="url"),
    html.Div(id="page-content")
])

# ------------------------ Routing ------------------------
@dash_app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    if not session.get("logged_in"):
        return dcc.Location(pathname="/login", id="redirect")

    if pathname in ["/dash/", "/dash"]:
        return main_layout(dashboard_home())
    if pathname == "/dash/chat":
        return main_layout(chat_page())
    if pathname == "/dash/data":
        return main_layout(data_page())

    return main_layout(html.H4("❌ Page not found"))

# ------------------------ Fake AI Callback ------------------------
@dash_app.callback(
    Output("ai-output", "children"),
    Input("send-btn", "n_clicks"),
    Input("user-input", "value"),
    prevent_initial_call=True
)
def fake_ai(n, text):
    if not text:
        return ""
    return f"🤖 AI received: {text}"
