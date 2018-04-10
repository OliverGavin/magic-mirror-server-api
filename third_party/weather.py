# simple example lambda script that could be used for third party integration


def weather_handler(event, env):
    context = event['context']

    if context == 'info':
        weather_info_handler(event)
    elif context == 'menu':
        weather_menu_handler(event)
    elif context == 'app':
        weather_app_handler(event)
    elif context == 'widget':
        weather_widget_handler(event)


def weather_info_handler(event):
    ...


def weather_menu_handler(event):
    ...


def weather_app_handler(event):
    ...


def weather_widget_handler(event):
    return {
        'title': 'Weather',
        'icon': 'sunny',
        'secondaryText': '5°C Sunny',
        'tertiaryText': 'Limerick',
        'template': 'circle'
    }
