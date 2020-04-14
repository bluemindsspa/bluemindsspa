odoo.define('gws_google_maps.view_registry', function (require) {
    "use strict";

    var MapView = require('gws_google_maps.MapView');
    var view_registry = require('web.view_registry');

    view_registry.add('map', MapView);

});
