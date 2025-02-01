import { reactive, computed } from 'vue'
import { createResource } from 'frappe-ui'

const checkinListResource = createResource('ess.api.employee.get_employee_checkin')
const addCheckinResource = createResource({
	url: 'ess.api.employee.add_checkin'
})

export function useCheckin() {
	const checkins = reactive({
		list: computed(() => checkinListResource.data),
		loading: computed(() => checkinListResource.loading),
		error: computed(() => checkinListResource.error),
		refresh: () => checkinListResource.fetch(),
		add: (log_type,work_from,lattitude,longitude) => addCheckinResource.submit({ log_type,work_from,lattitude,longitude }).then(() => checkinListResource.fetch()),
	})

	return checkins
}