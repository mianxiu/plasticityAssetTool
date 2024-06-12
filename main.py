import webview

def custom_logic(window):
    #window.toggle_fullscreen()
    window.evaluate_js('alert("Nice one brother")')

window = webview.create_window('Woah dude!', "dist/index.html")
webview.start(custom_logic, window)
# anything below this line will be executed after program is finished executing
pass