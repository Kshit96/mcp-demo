"""
        Generate content returns something like this:
        GenerateContentResponse(
            done=True,
            iterator=None,
            result=protos.GenerateContentResponse({
            "candidates": [
                {
                "content": {
                    "parts": [
                    {
                        "function_call": {
                        "name": "fetch_data",
                        "args": {
                            "endpoint": "https://meowfacts.herokuapp.com/",
                            "id": 3.0
                        }
                        }
                    }
                    ],
                    "role": "model"
                },
                "finish_reason": "STOP",
                "avg_logprobs": -0.029699273904164634
                }
            ],
            "usage_metadata": {
                "prompt_token_count": 108,
                "candidates_token_count": 15,
                "total_token_count": 123
            },
            "model_version": "gemini-2.0-flash"
            }),
        )
        —use .text for the “easy button,” or iterate candidates → content → parts when you need exact control (e.g., to detect and run tool calls).
        """

"""
                CallToolResult(
                    content=[
                                TextContent(
                                    type='text', 
                                    text='{
                                            "status":200,
                                            "url":"https://meowfacts.herokuapp.com/?count=3",
                                            "query":{"count":3},
                                            "data":
                                                {
                                                    "data":
                                                        [
                                                            "<Cat Fact 1>",
                                                            "<Cat Fact 2>",
                                                            "<Cat Fact 3>"
                                                        ]
                                                }
                                            }', 
                                            annotations=None, 
                                            meta=None
                                )
                            ],
                    structured_content=
                        {
                            'data': 
                                {
                                    'data': 
                                        [
                                            '<Cat Fact 1>',
                                            '<Cat Fact 2>',
                                            '<Cat Fact 3>'
                                        ]
                                },
                            'query': {'count': 3},
                            'status': 200,
                            'url': 'https://meowfacts.herokuapp.com/?count=3'},
                    data=
                        {
                            'data': 
                                {
                                    'data': 
                                        [
                                            '<Cat Fact 1>',
                                            '<Cat Fact 2>',
                                            '<Cat Fact 3>'
                                        ]
                                },
                            'query': {'count': 3},
                            'status': 200,
                            'url': 'https://meowfacts.herokuapp.com/?count=3'
                        },
                    is_error=False)
                """

"""
        [
            name: "fetch_data"
            args {
                fields {
                    key: "endpoint"
                    value {
                    string_value: "https://meowfacts.herokuapp.com/"
                    }
                }
                fields {
                    key: "count"
                    value {
                    number_value: 3
                    }
                }
            }
        ]
        """

MCP returns a list of tool objects of the format:
        [
            Tool(
                name='fetch_data', 
                title=None, 
                description='Fetch data from a public API endpoint.\nExample: endpoint="https://meowfacts.herokuapp.com/"\n\nOptional query parameters:\n    count (int): number of items to fetch\n    id (int): specific record ID\n    lang (str): language code', 
                inputSchema=
                    {
                        'properties': 
                            {
                                'endpoint': {'type': 'string'}, 
                                'count': {'anyOf': [{'type': 'integer'}, {'type': 'string'}, {'type': 'null'}], 'default': None}, 
                                'id': {'anyOf': [{'type': 'integer'}, {'type': 'null'}], 'default': None}, 
                                'lang': {'anyOf': [{'type': 'string'}, {'type': 'null'}], 'default': None}
                            }, 
                        'required': ['endpoint'], 
                        'type': 'object'
                    }, 
                    outputSchema=None, 
                    icons=None, 
                    annotations=None, 
                    meta={'_fastmcp': {'tags': []}}
                )
        ]

        Gemini Tools list is of the format:
        [
            {
                'description': 
                    'Fetch data from a public API endpoint.\n'
                    'Example: endpoint="https://meowfacts.herokuapp.com/"\n'
                    '\n'
                    'Optional query parameters:\n'
                    '    count (int): number of items to fetch\n'
                    '    id (int): specific record ID\n'
                    '    lang (str): language code',
                'name': 'fetch_data',
                'parameters': 
                    {
                        'properties': 
                            {
                                'count': {'type': 'NUMBER'},
                                'endpoint': {'type': 'STRING'},
                                'id': {'type': 'NUMBER'},
                                'lang': {'type': 'STRING'}
                            },
                        'required': ['endpoint'],
                        'type': 'OBJECT'
                    }
            }
        ]
        """

Expected MCP shape (simplified):
      {
        "name": "fetch_data",
        "description": "…",
        "inputSchema": {
          "type": "object",
          "properties": { "endpoint": {...}, ... },
          "required": ["endpoint"]
        }
      }
    Returns:
      {
        "name": "fetch_data",
        "description": "...",
        "parameters": {
          "type": "OBJECT",
          "properties": { "endpoint": { "type": "STRING", ... } },
          "required": ["endpoint"]
        }
      }
    """