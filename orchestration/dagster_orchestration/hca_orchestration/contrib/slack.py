

def key_value_slack_blocks(title: str, key_values: dict[str, str]) -> list[dict[str, object]]:
    """
    Creates a slack [blocks](https://api.slack.com/block-kit/building) structure that captures
    the supplied key-value information.
    """
    return [
        {
            "type": "section",
            "text": {
                'type': 'mrkdwn',
                'text': f'*{title}*',
            }
        },
        {
            'type': 'divider'
        },
        {
            'type': 'section',
            'fields': [
                {
                    'type': 'mrkdwn',
                    'text': '\n'.join(map(lambda keys: f'*{keys}*', key_values.keys())),
                },
                {
                    'type': 'mrkdwn',
                    'text': '\n'.join(key_values.values())
                }
            ]
        }
    ]