import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    implicitWidth: 428
    implicitHeight: 150

    signal accepted()
    signal rejected()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4

        // Row 1: Use paralyzable dead time checkbox
        RowLayout {
            Layout.fillWidth: true

            CheckBox {
                id: useParalyzableCheckbox
                objectName: "use_paralyzable"
                checked: true
            }

            Label {
                text: "Use paralyzable dead time"
                ToolTip.text: "Use the paralyzable (extendable) dead time correction model, where events arriving during the dead time period extend it"
                ToolTip.visible: hovered
                ToolTip.delay: 500
            }

            Item {
                Layout.fillWidth: true
            }
        }

        // Row 2: Dead time value [us]
        RowLayout {
            Layout.fillWidth: true

            Label {
                text: "Dead time value [us]"
            }

            Item {
                Layout.fillWidth: true
            }

            // SpinBox scaled by 10 to represent one decimal place (e.g. value=42 means 4.2)
            SpinBox {
                id: deadTimeValueSpinBox
                objectName: "dead_time_value"
                from: 0
                to: 100000
                value: 42
                stepSize: 1
                implicitWidth: 130

                property int decimals: 1

                validator: DoubleValidator {
                    bottom: Math.min(deadTimeValueSpinBox.from, deadTimeValueSpinBox.to)
                    top: Math.max(deadTimeValueSpinBox.from, deadTimeValueSpinBox.to)
                }

                textFromValue: function(value, locale) {
                    return Number(value / 10.0).toLocaleString(locale, 'f', decimals)
                }

                valueFromText: function(text, locale) {
                    return Math.round(Number.fromLocaleString(locale, text) * 10.0)
                }
            }
        }

        // Row 3: TOF binning use for correction [us]
        RowLayout {
            Layout.fillWidth: true

            Label {
                text: "TOF binning use for correction [us]"
            }

            Item {
                Layout.fillWidth: true
            }

            SpinBox {
                id: deadTimeTofSpinBox
                objectName: "dead_time_tof"
                from: 0
                to: 10000000
                value: 100
                stepSize: 50
                implicitWidth: 130
            }
        }

        // Row 4: OK / Cancel buttons
        DialogButtonBox {
            Layout.fillWidth: true
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel

            onAccepted: root.accepted()
            onRejected: root.rejected()
        }
    }
}
