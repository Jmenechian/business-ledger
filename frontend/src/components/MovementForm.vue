<script setup lang="ts">
import { computed, reactive } from "vue";
import { ArrowRight, Info } from "@lucide/vue";
import FormDialog from "./FormDialog.vue";
import PriceSuggestions from "./PriceSuggestions.vue";
import type { SuggestionLoader } from "../composables/usePriceSuggestions";
import type { Client, Movement, MovementInput, MovementKind } from "../types";
import {
  adjustPrice,
  deliveryTotal,
  money,
  positiveInteger,
} from "../utils/format";

const props = defineProps<{
  client: Client;
  kind: MovementKind;
  row?: Movement;
  input?: MovementInput;
  busy: boolean;
  error: string;
  uncertain: boolean;
  loadSuggestions?: SuggestionLoader;
}>();
const emit = defineEmits<{ save: [input: MovementInput]; close: [] }>();
const form = reactive({
  detalle: props.input?.detalle ?? props.row?.detalle ?? "",
  cant: String(props.input?.cant ?? props.row?.cant ?? ""),
  precio: String(
    props.input?.precio_unitario ?? props.row?.precio_unitario ?? "",
  ),
  haber: String(props.input?.haber ?? props.row?.haber ?? ""),
  n_remito: props.input?.n_remito ?? props.row?.n_remito ?? "",
  fecha: props.input?.fecha ?? props.row?.fecha ?? "",
  validation: "",
});
const total = computed(() => {
  try {
    return props.kind === "delivery"
      ? deliveryTotal(
          positiveInteger(form.cant, "Cantidad"),
          positiveInteger(form.precio, "Precio unitario"),
        )
      : positiveInteger(form.haber, "Importe");
  } catch {
    return null;
  }
});
function changePrice(percentage: number) {
  try {
    form.precio = String(
      adjustPrice(positiveInteger(form.precio, "Precio"), percentage),
    );
    form.validation = "";
  } catch (error) {
    form.validation = (error as Error).message;
  }
}
function submit() {
  form.validation = "";
  try {
    if (props.uncertain && props.input) {
      emit("save", props.input);
      return;
    }
    const input: MovementInput = {
      detalle: form.detalle.trim() || (props.kind === "payment" ? "Pago" : ""),
      n_remito: form.n_remito.trim(),
      fecha: form.fecha,
    };
    if (!input.detalle) throw new Error("Ingresá el detalle de la entrega.");
    if (props.kind === "delivery") {
      input.cant = positiveInteger(form.cant, "Cantidad");
      input.precio_unitario = positiveInteger(form.precio, "Precio unitario");
      deliveryTotal(input.cant, input.precio_unitario);
    } else input.haber = positiveInteger(form.haber, "Importe");
    emit("save", input);
  } catch (error) {
    form.validation = (error as Error).message;
  }
}
</script>
<template>
  <FormDialog
    :title="
      row
        ? 'Editar movimiento'
        : kind === 'delivery'
          ? 'Nueva entrega'
          : 'Registrar pago'
    "
    :subtitle="client.nombre"
    :busy="busy"
    @close="emit('close')"
    ><form @submit.prevent="submit">
      <div class="dialog-body">
        <p v-if="uncertain" class="notice">
          <Info :size="17" /> El envío está sin confirmar. Reintentaremos los
          mismos datos, sin duplicar el movimiento.
        </p>
        <fieldset :disabled="busy || uncertain">
          <label v-if="kind === 'delivery'" for="movement-detail"
            >Detalle <span class="required">*</span></label
          ><label v-else for="movement-detail"
            >Detalle <span class="optional">opcional</span></label
          ><input
            id="movement-detail"
            v-model="form.detalle"
            autofocus
            :required="kind === 'delivery'"
            maxlength="500"
            :placeholder="
              kind === 'delivery' ? 'Ej.: Remeras de algodón · costura' : 'Pago'
            "
          />
          <PriceSuggestions
            v-if="kind === 'delivery' && !row && !uncertain && loadSuggestions"
            :client="client.id"
            :query="form.detalle"
            :load="loadSuggestions"
            @select="
              (reference) => (form.precio = String(reference.precio_unitario))
            "
          />
          <div v-if="kind === 'delivery'" class="field-grid">
            <div>
              <label for="quantity"
                >Cantidad <span class="required">*</span></label
              ><input
                id="quantity"
                v-model="form.cant"
                inputmode="numeric"
                pattern="[0-9]+"
                required
                placeholder="0"
              />
            </div>
            <div>
              <label for="price"
                >Precio unitario <span class="required">*</span></label
              >
              <div class="money-input">
                <span>$</span
                ><input
                  id="price"
                  v-model="form.precio"
                  inputmode="numeric"
                  pattern="[0-9]+"
                  required
                  placeholder="0"
                />
              </div>
            </div>
          </div>
          <div v-if="kind === 'delivery'" class="price-adjustments">
            <span>Ajustar precio</span
            ><button type="button" @click="changePrice(5)">+5 %</button
            ><button type="button" @click="changePrice(10)">+10 %</button
            ><small>Redondeado a entero</small>
          </div>
          <div v-else>
            <label for="payment-amount"
              >Importe recibido <span class="required">*</span></label
            >
            <div class="money-input">
              <span>$</span
              ><input
                id="payment-amount"
                v-model="form.haber"
                inputmode="numeric"
                pattern="[0-9]+"
                required
                placeholder="0"
              />
            </div>
          </div>
          <div class="field-grid optional-fields">
            <div>
              <label for="reference"
                >N° de remito <span class="optional">opcional</span></label
              ><input
                id="reference"
                v-model="form.n_remito"
                maxlength="100"
                placeholder="Ej.: R-001"
              />
            </div>
            <div>
              <label for="business-date"
                >Fecha <span class="optional">opcional</span></label
              ><input
                id="business-date"
                v-model="form.fecha"
                type="date"
                min="0001-01-01"
                max="9999-12-31"
              />
            </div>
          </div>
        </fieldset>
        <div class="form-total">
          <span
            >{{ kind === "delivery" ? "Total de la entrega" : "Total del pago"
            }}<small>Importes enteros, sin centavos</small></span
          ><strong>{{ total === null ? "$ —" : money(total) }}</strong>
        </div>
        <p v-if="form.validation || error" class="form-error" role="alert">
          {{ form.validation || error }}
        </p>
      </div>
      <footer class="dialog-footer">
        <button
          type="button"
          class="button secondary"
          :disabled="busy"
          @click="emit('close')"
        >
          {{ uncertain ? "Volver a la cuenta" : "Cancelar" }}</button
        ><button class="button primary" :disabled="busy">
          {{
            busy
              ? "Guardando…"
              : uncertain
                ? "Reintentar envío"
                : row
                  ? "Guardar cambios"
                  : kind === "delivery"
                    ? "Guardar entrega"
                    : "Guardar pago"
          }}<ArrowRight v-if="!busy" :size="16" />
        </button>
      </footer></form
  ></FormDialog>
</template>
