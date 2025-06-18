$(document).ready(function() {
    $('input[name="answer_id"]').change(function() {
        $('#answer-form button').prop('disabled', false);
    });
});