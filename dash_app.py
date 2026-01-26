import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html
from openai import OpenAI


# ---------------------------
# Create Dash App (IMPORTANT)
# ---------------------------
def create_dash_app(flask_app):

    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname="/dash/",
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True
    )

    dash_app.title = "DeepSeek AI Chat"

    # ---------------------------
    # Layout
    # ---------------------------
    dash_app.layout = dbc.Container([
        html.H1("🤖 DeepSeek AI Chat Interface", className="text-center my-4"),

        dbc.Row([
            dbc.Col([
                dbc.Input(id="api-key", type="password", placeholder="Enter your API key"),
                html.Br(),
                dcc.Dropdown(
                    id="model-choice",
                    options=[
                        {"label": "deepseek-chat", "value": "deepseek-chat"},
                        {"label": "deepseek-coder", "value": "deepseek-coder"}
                    ],
                    value="deepseek-chat",
                    clearable=False
                ),
                html.Br(),
                dcc.Slider(id="temperature", min=0.1, max=2.0, step=0.1, value=0.7),
                html.Br(),
                dcc.Slider(id="max-tokens", min=100, max=4096, step=100, value=1024),
                html.Br(),
                dbc.Button("Clear Chat", id="clear-chat-btn", color="secondary"),
                html.Div(id="status", className="mt-2")
            ], width=4),

            dbc.Col([
                html.Div(id="chat-window", style={
                    "border": "1px solid #ccc",
                    "height": "500px",
                    "overflowY": "scroll",
                    "padding": "10px"
                }),
                html.Br(),
                dbc.Input(id="user-msg", placeholder="Type message..."),
                html.Br(),
                dbc.Button("Send", id="send-btn", color="primary")
            ], width=8)
        ]),

        dcc.Store(id="chat-history", data=[])
    ])

    # ---------------------------
    # Callbacks
    # ---------------------------
    @dash_app.callback(
        Output("chat-history", "data"),
        Output("chat-window", "children"),
        Input("clear-chat-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def clear_chat(n):
        return [], []

    return dash_app
