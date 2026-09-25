import Highcharts from "highcharts";
import exportingInit from "highcharts/modules/exporting";
import exportDataInit from "highcharts/modules/export-data";
import offlineExportingInit from "highcharts/modules/offline-exporting";
import labelInit from "highcharts/modules/series-label";

exportingInit(Highcharts);
exportDataInit(Highcharts);
offlineExportingInit(Highcharts);
labelInit(Highcharts);

export default Highcharts;
