/* rophako cms
   -----------
   Script for /account/setup
*/

$(document).ready(function() {
    $("#setup_form").submit(function() {
        var username = $("#username").val(),
            pw1 = $("#pw1").val(),
            pw2 = $("#pw2").val();

        if (username.length === 0) {
            window.alert("The username is required.");
        }
        else if (username.match(/[^A-Za-z0-9_-]+/)) {
            window.alert("The username should only contain numbers, letters, underscores or dashes.");
        }
        else if (pw1.length < 3) {
            window.alert("Your password should have at least three characters.");
        }
        else if (pw1 !== pw2) {
            window.alert("Your passwords don't match.");
        }
        else {
            // All good!
            return true;
        }

        return false;
    });
})