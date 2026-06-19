(function() {
    var baseUrl = '/admin/portal/placementrecord/';

    function fillStudentDetails(studentId) {
        if (!studentId) return;
        fetch(baseUrl + 'student-details/' + studentId + '/')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.error) return;
                setFieldValue('student_name', data.name);
                setFieldValue('aadhaar', data.roll_number);
                setFieldValue('course_name', data.course_name);
                setFieldValue('batch_code', data.batch_code);
                setFieldValue('center_name', data.center_name);
            })
            .catch(function(e) {});
    }

    function setFieldValue(name, value) {
        var el = document.querySelector('[name="' + name + '"]');
        if (el) el.value = value || '';
    }

    function init() {
        var studentField = document.querySelector('select[name="student"]');
        if (!studentField) return;

        function handleChange() {
            var val = studentField.value;
            if (val) fillStudentDetails(val);
        }

        studentField.addEventListener('change', handleChange);
        studentField.addEventListener('select2:select', handleChange);

        if (studentField.value) fillStudentDetails(studentField.value);
    }

    if (document.readyState === 'complete') {
        setTimeout(init, 300);
    } else {
        window.addEventListener('load', function() { setTimeout(init, 300); });
    }
})();
