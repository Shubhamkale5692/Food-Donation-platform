import os

app_js_path = r'f:\Food Donation Platform\frontend\app\app.js'
with open(app_js_path, 'r', encoding='utf-8') as f:
    app_js = f.read()

old_str = '''        var loginUrl = (typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : "/api") + "/login";

        $http.post(loginUrl, $scope.loginData)
        .then(function(res) {
            if (res.data && res.data.success) {
                var t = res.data.token || res.data.access_token;'''

new_str = '''        var loginUrl = (typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : "/api") + "/login";
        console.log("Login request:", $scope.loginData.email);

        $http.post(loginUrl, $scope.loginData)
        .then(function(res) {
            console.log("API response:", res.data);
            if (res.data && res.data.success) {
                var t = res.data.token || res.data.access_token;
                console.log("Token value:", t);'''

app_js = app_js.replace(old_str, new_str)
app_js = app_js.replace(old_str.replace('\n', '\r\n'), new_str)

with open(app_js_path, 'w', encoding='utf-8') as f:
    f.write(app_js)

print('Added debug logging')
